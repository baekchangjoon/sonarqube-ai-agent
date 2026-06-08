import pytest
from unittest.mock import MagicMock, patch

from src.agents.base import AgentType, FixResult
from src.config import (
    AgentConfig, AppConfig, NightlyBatchConfig, PostMergeConfig,
    PrPremergeConfig, ScannerConfig, AssessmentConfig, SonarQubeConfig,
)
from src.github_client import GitHubClient
from src.orchestrator import SonarQubeOrchestrator
from src.sonarqube_client import SonarIssue


def _make_config(**overrides) -> AppConfig:
    defaults = {
        "agent": AgentConfig(type="claude-code"),
        "sonarqube": SonarQubeConfig(
            url="http://localhost:9000",
            token="test-token",
            main_project_key="test-project",
        ),
        "scanner": ScannerConfig(),
        "pr_premerge": PrPremergeConfig(),
        "post_merge": PostMergeConfig(),
        "nightly_batch": NightlyBatchConfig(),
    }
    defaults.update(overrides)
    return AppConfig(**defaults)


def _make_issue(key="K1", rule="java:S2259", severity="CRITICAL",
                issue_type="BUG", line=10,
                file_path="src/main/java/Foo.java") -> SonarIssue:
    return SonarIssue(
        key=key, rule=rule, severity=severity,
        component=f"test-project:{file_path}",
        line=line, message=f"Issue {key}",
        issue_type=issue_type, file_path=file_path,
    )


def _make_orchestrator(config=None):
    with patch("src.orchestrator.AgentFactory") as mock_factory:
        mock_agent = MagicMock()
        mock_agent.name.return_value = "Mock Agent"
        mock_agent.generate_fix.return_value = "fixed code"
        mock_agent.build_fix_prompt.return_value = "prompt"
        mock_agent.get_usage.return_value = {
            "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0,
        }
        mock_factory.create.return_value = mock_agent
        orch = SonarQubeOrchestrator(config or _make_config())
    orch._sonar = MagicMock()
    orch._github = MagicMock()
    return orch


class TestJudgeAgentRouting:
    """구성 A: fixer and judge can be different agents."""

    def _make_split_orchestrator(self):
        config = _make_config(
            agent=AgentConfig(type="claude-code", judge_type="bedrock-api"),
            assessment=AssessmentConfig(strategy="triage"),
        )
        fixer, judge = MagicMock(), MagicMock()
        fixer.name.return_value = "Fixer"
        judge.name.return_value = "Judge"
        fixer.generate_fix.return_value = "fixed code"
        judge.generate_triage.return_value = (
            '{"verdict": "TRUE_POSITIVE", "confidence": 0.9, "reason": "r"}'
        )
        for m in (fixer, judge):
            m.get_usage.return_value = {
                "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0,
            }
        with patch("src.orchestrator.AgentFactory") as mock_factory:
            mock_factory.create.side_effect = [fixer, judge]
            orch = SonarQubeOrchestrator(config)
        orch._sonar = MagicMock()
        orch._github = MagicMock()
        orch._sonar.get_source_lines.return_value = ["line"]
        return orch, fixer, judge

    def test_judge_created_with_overrides(self):
        config = _make_config(
            agent=AgentConfig(type="claude-code",
                              judge_type="bedrock-api",
                              judge_model="m1"),
        )
        with patch("src.orchestrator.AgentFactory") as mock_factory:
            mock_factory.create.return_value = MagicMock()
            SonarQubeOrchestrator(config)
        assert mock_factory.create.call_count == 2
        judge_call = mock_factory.create.call_args_list[1]
        assert judge_call[1]["agent_type"] == "bedrock-api"
        assert judge_call[1]["model"] == "m1"

    def test_no_judge_config_reuses_fix_agent(self):
        orch = _make_orchestrator()
        assert orch._judge is orch._agent

    def test_triage_goes_to_judge_fix_goes_to_fixer(self):
        orch, fixer, judge = self._make_split_orchestrator()

        fixes, skipped = orch._triage_and_fix(
            [_make_issue("K1")], "/tmp/proj")

        judge.generate_triage.assert_called_once()
        fixer.generate_fix.assert_called_once()
        fixer.generate_triage.assert_not_called()
        assert len(fixes) == 1 and not skipped

    def test_judge_model_only_override(self):
        config = _make_config(
            agent=AgentConfig(type="claude-code", judge_model="opus"),
        )
        with patch("src.orchestrator.AgentFactory") as mock_factory:
            mock_factory.create.return_value = MagicMock()
            SonarQubeOrchestrator(config)
        judge_call = mock_factory.create.call_args_list[1]
        assert judge_call[1]["agent_type"] is None
        assert judge_call[1]["model"] == "opus"


class TestOrchestratorEphemeralKey:

    def test_ephemeral_key_format(self):
        config = _make_config()
        with patch.object(SonarQubeOrchestrator, "__init__", lambda s, c: None):
            orch = SonarQubeOrchestrator.__new__(SonarQubeOrchestrator)
            orch._config = config
        key = orch._ephemeral_key(42)
        assert key == "test-project-pr-42"


@patch("src.orchestrator.time.sleep")
class TestOrchestratorPrPremergeEphemeral:

    def test_ephemeral_creates_and_scans_temp_project(self, _sleep):
        orch = _make_orchestrator()
        orch._sonar.run_scanner.return_value = True
        orch._sonar.get_open_issues.side_effect = [
            [_make_issue("K1")],  # initial scan
            [],                   # verification re-scan: issue resolved
        ]
        orch._sonar.get_quality_gate_status.return_value = "ERROR"
        orch._sonar.get_source_lines.return_value = ["line"]

        result = orch.handle_pr_premerge("o/r", 42, "/tmp/proj")

        orch._sonar.create_project.assert_called_once()
        assert result.project_key == "test-project-pr-42"
        assert result.issues_found == 1
        assert result.fixes_attempted == 1
        assert result.fixes_verified == 1

    def test_verification_counts_only_resolved_issues(self, _sleep):
        orch = _make_orchestrator()
        orch._sonar.run_scanner.return_value = True
        orch._sonar.get_open_issues.side_effect = [
            [_make_issue("K1"), _make_issue("K2")],
            [_make_issue("K2")],  # K2 still open after fix
        ]
        orch._sonar.get_quality_gate_status.return_value = "ERROR"
        orch._sonar.get_source_lines.return_value = ["line"]

        result = orch.handle_pr_premerge("o/r", 1, "/tmp/proj")

        assert result.fixes_attempted == 2
        assert result.fixes_verified == 1

    def test_max_issues_per_run_limits_fixes(self, _sleep):
        config = _make_config(
            pr_premerge=PrPremergeConfig(max_issues_per_run=1),
        )
        orch = _make_orchestrator(config)
        orch._sonar.run_scanner.return_value = True
        orch._sonar.get_open_issues.side_effect = [
            [_make_issue("K1"), _make_issue("K2"), _make_issue("K3")],
            [],
        ]
        orch._sonar.get_quality_gate_status.return_value = "ERROR"
        orch._sonar.get_source_lines.return_value = ["line"]

        result = orch.handle_pr_premerge("o/r", 1, "/tmp/proj")

        assert result.fixes_attempted == 1

    def test_delivery_comment_posts_to_github(self, _sleep):
        config = _make_config(
            pr_premerge=PrPremergeConfig(delivery="comment"),
        )
        orch = _make_orchestrator(config)
        orch._sonar.run_scanner.return_value = True
        orch._sonar.get_open_issues.side_effect = [[_make_issue("K1")], []]
        orch._sonar.get_quality_gate_status.return_value = "ERROR"
        orch._sonar.get_source_lines.return_value = ["line"]
        orch._github.comment_on_pr.return_value = True

        orch.handle_pr_premerge("owner/repo", 7, "/tmp/proj")

        orch._github.comment_on_pr.assert_called_once()
        call_args = orch._github.comment_on_pr.call_args
        assert call_args[0][0] == "owner/repo"
        assert call_args[0][1] == 7

    def test_delivery_log_does_not_post(self, _sleep):
        config = _make_config(
            pr_premerge=PrPremergeConfig(delivery="log"),
        )
        orch = _make_orchestrator(config)
        orch._sonar.run_scanner.return_value = True
        orch._sonar.get_open_issues.side_effect = [[_make_issue("K1")], []]
        orch._sonar.get_quality_gate_status.return_value = "ERROR"
        orch._sonar.get_source_lines.return_value = ["line"]

        orch.handle_pr_premerge("owner/repo", 7, "/tmp/proj")

        orch._github.comment_on_pr.assert_not_called()

    def test_disabled_mode_skips_scan(self, _sleep):
        config = _make_config(
            pr_premerge=PrPremergeConfig(enabled=False),
        )
        orch = _make_orchestrator(config)

        result = orch.handle_pr_premerge("o/r", 1, "/tmp/proj")

        assert result.quality_gate == "DISABLED"
        orch._sonar.run_scanner.assert_not_called()

    def test_push_fix_commit_pushes_to_pr_branch(self, _sleep):
        config = _make_config(
            pr_premerge=PrPremergeConfig(push_fix_commit=True,
                                         delivery="log"),
        )
        orch = _make_orchestrator(config)
        orch._sonar.run_scanner.return_value = True
        orch._sonar.get_open_issues.side_effect = [[_make_issue("K1")], []]
        orch._sonar.get_quality_gate_status.return_value = "ERROR"
        orch._sonar.get_source_lines.return_value = ["line"]
        orch._github.commit_and_push.return_value = True

        orch.handle_pr_premerge("o/r", 9, "/tmp/proj")

        orch._github.commit_and_push.assert_called_once()
        args = orch._github.commit_and_push.call_args[0]
        assert args[0] == "/tmp/proj"
        assert "PR #9" in args[1]

    def test_push_fix_commit_default_off(self, _sleep):
        orch = _make_orchestrator()
        orch._sonar.run_scanner.return_value = True
        orch._sonar.get_open_issues.side_effect = [[_make_issue("K1")], []]
        orch._sonar.get_quality_gate_status.return_value = "ERROR"
        orch._sonar.get_source_lines.return_value = ["line"]

        orch.handle_pr_premerge("o/r", 9, "/tmp/proj")

        orch._github.commit_and_push.assert_not_called()

    def test_push_fix_commit_skipped_without_verified(self, _sleep):
        config = _make_config(
            pr_premerge=PrPremergeConfig(push_fix_commit=True,
                                         delivery="log"),
        )
        orch = _make_orchestrator(config)
        orch._sonar.run_scanner.return_value = True
        orch._sonar.get_open_issues.side_effect = [
            [_make_issue("K1")],
            [_make_issue("K1")],  # still open — not verified
        ]
        orch._sonar.get_quality_gate_status.return_value = "ERROR"
        orch._sonar.get_source_lines.return_value = ["line"]

        orch.handle_pr_premerge("o/r", 9, "/tmp/proj")

        orch._github.commit_and_push.assert_not_called()


@patch("src.orchestrator.time.sleep")
class TestOrchestratorPrPremergeNative:

    def _native_config(self, **pr_overrides):
        return _make_config(
            scanner=ScannerConfig(pr_mode="native"),
            pr_premerge=PrPremergeConfig(**pr_overrides),
        )

    def test_native_scans_with_pullrequest_params(self, _sleep):
        orch = _make_orchestrator(self._native_config())
        orch._sonar.run_scanner.return_value = True
        orch._sonar.get_open_issues.side_effect = [[_make_issue("K1")], []]
        orch._sonar.get_quality_gate_status.return_value = "OK"
        orch._sonar.get_source_lines.return_value = ["line"]

        result = orch.handle_pr_premerge(
            "o/r", 42, "/tmp/proj",
            pr_branch="feature/x", pr_base="develop",
        )

        # no ephemeral project lifecycle
        orch._sonar.create_project.assert_not_called()
        assert result.project_key == "test-project"

        extra = orch._sonar.run_scanner.call_args_list[0][1]["extra_args"]
        assert "-Dsonar.pullrequest.key=42" in extra
        assert "-Dsonar.pullrequest.branch=feature/x" in extra
        assert "-Dsonar.pullrequest.base=develop" in extra

        # issues and gate fetched for the PR slot
        issues_kwargs = orch._sonar.get_open_issues.call_args_list[0][1]
        assert issues_kwargs["pull_request"] == "42"
        gate_kwargs = orch._sonar.get_quality_gate_status.call_args[1]
        assert gate_kwargs["pull_request"] == "42"

    def test_native_verification_rescans_pr_slot(self, _sleep):
        orch = _make_orchestrator(self._native_config())
        orch._sonar.run_scanner.return_value = True
        orch._sonar.get_open_issues.side_effect = [
            [_make_issue("K1"), _make_issue("K2")],
            [_make_issue("K2")],
        ]
        orch._sonar.get_quality_gate_status.return_value = "OK"
        orch._sonar.get_source_lines.return_value = ["line"]

        result = orch.handle_pr_premerge("o/r", 5, "/tmp/proj")

        assert orch._sonar.run_scanner.call_count == 2  # initial + verify
        assert result.fixes_verified == 1

    def test_native_cleanup_is_noop(self, _sleep):
        orch = _make_orchestrator(self._native_config())
        assert orch.cleanup_pr_project(42) is True
        orch._sonar.delete_project.assert_not_called()


@patch("src.orchestrator.time.sleep")
class TestOrchestratorPostMerge:

    def test_post_merge_no_issues(self, _sleep):
        orch = _make_orchestrator()
        orch._sonar.get_new_issues.return_value = []
        orch._sonar.get_quality_gate_status.return_value = "OK"

        result = orch.handle_post_merge()

        assert result.mode == "post_merge"
        assert result.issues_found == 0
        assert result.quality_gate == "OK"
        orch._agent.generate_fix.assert_not_called()

    def test_post_merge_without_project_dir_is_unverified(self, _sleep):
        orch = _make_orchestrator()
        orch._sonar.get_new_issues.return_value = [
            _make_issue("K1"), _make_issue("K2"),
        ]
        orch._sonar.get_quality_gate_status.return_value = "ERROR"
        orch._sonar.get_source_lines.return_value = ["line1", "line2"]

        result = orch.handle_post_merge()

        assert result.issues_found == 2
        assert result.fixes_attempted == 2
        assert result.fixes_verified == 0
        assert result.quality_gate == "ERROR"

    def test_post_merge_creates_fix_pr_when_configured(self, _sleep):
        config = _make_config(
            post_merge=PostMergeConfig(
                create_fix_pr=True,
                fix_pr_repo="owner/repo",
                fix_pr_base="develop",
            ),
        )
        orch = _make_orchestrator(config)
        orch._sonar.run_scanner.return_value = True
        orch._sonar.get_new_issues.return_value = [_make_issue("K1")]
        orch._sonar.get_open_issues.return_value = []  # verification
        orch._sonar.get_quality_gate_status.return_value = "ERROR"
        orch._sonar.get_source_lines.return_value = ["line"]
        orch._github.push_fix_branch.return_value = True
        orch._github.create_fix_pr.return_value = "https://pr/2"

        result = orch.handle_post_merge(project_dir="/tmp/proj")

        assert result.fixes_verified == 1
        branch = orch._github.push_fix_branch.call_args[0][1]
        assert "post-merge" in branch
        pr_kwargs = orch._github.create_fix_pr.call_args[1]
        assert pr_kwargs["repo"] == "owner/repo"
        assert pr_kwargs["base"] == "develop"

    def test_post_merge_no_fix_pr_by_default(self, _sleep):
        orch = _make_orchestrator()
        orch._sonar.run_scanner.return_value = True
        orch._sonar.get_new_issues.return_value = [_make_issue("K1")]
        orch._sonar.get_open_issues.return_value = []
        orch._sonar.get_quality_gate_status.return_value = "ERROR"
        orch._sonar.get_source_lines.return_value = ["line"]

        orch.handle_post_merge(project_dir="/tmp/proj")

        orch._github.push_fix_branch.assert_not_called()

    def test_post_merge_with_project_dir_verifies(self, _sleep):
        orch = _make_orchestrator()
        orch._sonar.run_scanner.return_value = True
        orch._sonar.get_new_issues.return_value = [_make_issue("K1")]
        orch._sonar.get_open_issues.return_value = []  # verification
        orch._sonar.get_quality_gate_status.return_value = "ERROR"
        orch._sonar.get_source_lines.return_value = ["line"]

        result = orch.handle_post_merge(project_dir="/tmp/proj")

        assert result.fixes_attempted == 1
        assert result.fixes_verified == 1
        # initial scan + verification re-scan
        assert orch._sonar.run_scanner.call_count == 2

    def test_disabled_mode(self, _sleep):
        config = _make_config(post_merge=PostMergeConfig(enabled=False))
        orch = _make_orchestrator(config)

        result = orch.handle_post_merge()

        assert result.quality_gate == "DISABLED"
        orch._sonar.get_new_issues.assert_not_called()


@patch("src.orchestrator.time.sleep")
class TestOrchestratorNightlyBatch:

    def test_nightly_batch_respects_severity_filter(self, _sleep):
        config = _make_config(
            nightly_batch=NightlyBatchConfig(
                severity_filter=["BLOCKER"],
                max_issues_per_run=5,
            ),
        )
        orch = _make_orchestrator(config)
        orch._sonar.get_open_issues.return_value = []
        orch._sonar.get_quality_gate_status.return_value = "OK"

        orch.handle_nightly_batch()

        orch._sonar.get_open_issues.assert_called_once_with(
            project_key="test-project",
            severities=["BLOCKER"],
            max_results=5,
        )

    def test_nightly_creates_fix_pr_when_configured(self, _sleep):
        config = _make_config(
            nightly_batch=NightlyBatchConfig(
                create_fix_pr=True,
                fix_pr_repo="owner/repo",
                fix_pr_base="main",
            ),
        )
        orch = _make_orchestrator(config)
        orch._sonar.run_scanner.return_value = True
        orch._sonar.get_open_issues.side_effect = [
            [_make_issue("K1")],  # batch selection
            [],                   # verification: resolved
        ]
        orch._sonar.get_quality_gate_status.return_value = "ERROR"
        orch._sonar.get_source_lines.return_value = ["line"]
        orch._github.push_fix_branch.return_value = True
        orch._github.create_fix_pr.return_value = "https://pr/1"

        result = orch.handle_nightly_batch(project_dir="/tmp/proj")

        assert result.fixes_verified == 1
        orch._github.push_fix_branch.assert_called_once()
        branch = orch._github.push_fix_branch.call_args[0][1]
        assert "nightly" in branch
        orch._github.create_fix_pr.assert_called_once()
        pr_kwargs = orch._github.create_fix_pr.call_args[1]
        assert pr_kwargs["repo"] == "owner/repo"
        assert pr_kwargs["base"] == "main"

    def test_nightly_skips_fix_pr_without_verified_fixes(self, _sleep):
        config = _make_config(
            nightly_batch=NightlyBatchConfig(
                create_fix_pr=True, fix_pr_repo="owner/repo",
            ),
        )
        orch = _make_orchestrator(config)
        orch._sonar.run_scanner.return_value = True
        orch._sonar.get_open_issues.side_effect = [
            [_make_issue("K1")],
            [_make_issue("K1")],  # still open — not verified
        ]
        orch._sonar.get_quality_gate_status.return_value = "ERROR"
        orch._sonar.get_source_lines.return_value = ["line"]

        result = orch.handle_nightly_batch(project_dir="/tmp/proj")

        assert result.fixes_verified == 0
        orch._github.push_fix_branch.assert_not_called()

    def test_nightly_default_does_not_create_pr(self, _sleep):
        orch = _make_orchestrator()
        orch._sonar.run_scanner.return_value = True
        orch._sonar.get_open_issues.side_effect = [[_make_issue("K1")], []]
        orch._sonar.get_quality_gate_status.return_value = "ERROR"
        orch._sonar.get_source_lines.return_value = ["line"]

        orch.handle_nightly_batch(project_dir="/tmp/proj")

        orch._github.push_fix_branch.assert_not_called()

    def test_disabled_mode(self, _sleep):
        config = _make_config(
            nightly_batch=NightlyBatchConfig(enabled=False),
        )
        orch = _make_orchestrator(config)

        result = orch.handle_nightly_batch()

        assert result.quality_gate == "DISABLED"
        orch._sonar.get_open_issues.assert_not_called()


@patch("src.orchestrator.time.sleep")
class TestFpTriage:

    def _triage_orch(self):
        config = _make_config(
            assessment=AssessmentConfig(strategy="triage"),
            pr_premerge=PrPremergeConfig(delivery="log"),
        )
        orch = _make_orchestrator(config)
        orch._sonar.run_scanner.return_value = True
        orch._sonar.get_quality_gate_status.return_value = "ERROR"
        orch._sonar.get_source_lines.return_value = ["line"]
        return orch

    def test_false_positive_skips_fix(self, _sleep):
        orch = self._triage_orch()
        orch._agent.generate_triage.return_value = (
            '{"verdict": "FALSE_POSITIVE", "confidence": 0.85, '
            '"reason": "field is used via reflection"}'
        )
        orch._sonar.get_open_issues.side_effect = [[_make_issue("K1")]]

        result = orch.handle_pr_premerge("o/r", 1, "/tmp/proj")

        orch._agent.generate_fix.assert_not_called()
        assert result.issues_skipped_as_fp == 1
        assert result.fixes_attempted == 0
        # no fixes → no verification re-scan
        assert orch._sonar.run_scanner.call_count == 1

    def test_true_positive_proceeds_to_fix(self, _sleep):
        orch = self._triage_orch()
        orch._agent.generate_triage.return_value = (
            '{"verdict": "TRUE_POSITIVE", "confidence": 0.9, '
            '"reason": "real resource leak"}'
        )
        orch._sonar.get_open_issues.side_effect = [[_make_issue("K1")], []]

        result = orch.handle_pr_premerge("o/r", 1, "/tmp/proj")

        orch._agent.generate_fix.assert_called_once()
        assert result.issues_skipped_as_fp == 0
        assert result.fixes_verified == 1

    def test_unparseable_triage_falls_back_to_fix(self, _sleep):
        orch = self._triage_orch()
        orch._agent.generate_triage.return_value = "I think it is fine."
        orch._sonar.get_open_issues.side_effect = [[_make_issue("K1")], []]

        result = orch.handle_pr_premerge("o/r", 1, "/tmp/proj")

        orch._agent.generate_fix.assert_called_once()
        assert result.issues_skipped_as_fp == 0

    def test_triage_disabled_skips_judgment(self, _sleep):
        orch = _make_orchestrator()  # triage default off
        orch._sonar.run_scanner.return_value = True
        orch._sonar.get_open_issues.side_effect = [[_make_issue("K1")], []]
        orch._sonar.get_quality_gate_status.return_value = "ERROR"
        orch._sonar.get_source_lines.return_value = ["line"]

        orch.handle_pr_premerge("o/r", 1, "/tmp/proj")

        orch._agent.generate_triage.assert_not_called()

    def test_fp_report_in_pr_comment(self, _sleep):
        config = _make_config(
            assessment=AssessmentConfig(strategy="triage"),
            pr_premerge=PrPremergeConfig(delivery="comment"),
        )
        orch = _make_orchestrator(config)
        orch._sonar.run_scanner.return_value = True
        orch._sonar.get_quality_gate_status.return_value = "ERROR"
        orch._sonar.get_source_lines.return_value = ["line"]
        orch._agent.generate_triage.return_value = (
            '{"verdict": "FALSE_POSITIVE", "confidence": 0.72, '
            '"reason": "test-only code"}'
        )
        orch._sonar.get_open_issues.side_effect = [[_make_issue("K1")]]
        orch._github.comment_on_pr.return_value = True

        orch.handle_pr_premerge("owner/repo", 3, "/tmp/proj")

        comment = orch._github.comment_on_pr.call_args[0][2]
        assert "False Positive Screening" in comment
        assert "0.72" in comment
        assert "test-only code" in comment

    def test_fix_confidence_in_commit_message(self, _sleep):
        config = _make_config(
            assessment=AssessmentConfig(strategy="triage"),
            pr_premerge=PrPremergeConfig(delivery="log",
                                         push_fix_commit=True),
        )
        orch = _make_orchestrator(config)
        orch._sonar.run_scanner.return_value = True
        orch._sonar.get_quality_gate_status.return_value = "ERROR"
        orch._sonar.get_source_lines.return_value = ["line"]
        orch._agent.generate_triage.return_value = (
            '{"verdict": "TRUE_POSITIVE", "confidence": 0.9, "reason": "r"}'
        )
        orch._agent.generate_fix.return_value = (
            'done\n{"fix_confidence": 0.8, "reason": "simple removal"}'
        )
        orch._sonar.get_open_issues.side_effect = [[_make_issue("K1")], []]
        orch._github.commit_and_push.return_value = True

        orch.handle_pr_premerge("o/r", 5, "/tmp/proj")

        message = orch._github.commit_and_push.call_args[0][1]
        assert "Fix confidence" in message
        assert "0.80" in message


@patch("src.orchestrator.time.sleep")
class TestPostReview:
    """Option D: fix-with-FP-escape + independent post-review."""

    def _review_orch(self, tmp_path, fix_side_effect):
        config = _make_config(
            assessment=AssessmentConfig(strategy="review"),
            pr_premerge=PrPremergeConfig(delivery="log"),
        )
        orch = _make_orchestrator(config)
        orch._sonar.run_scanner.return_value = True
        orch._sonar.get_quality_gate_status.return_value = "ERROR"
        orch._sonar.get_raw_source.return_value = ""  # window path
        orch._sonar.get_source_lines.return_value = ["line"]
        orch._agent.generate_fix.side_effect = fix_side_effect

        target = tmp_path / "src/main/java/Foo.java"
        target.parent.mkdir(parents=True)
        target.write_text("class Foo { int bad; }\n")
        return orch, target

    def test_applied_fix_gets_independent_review(self, _sleep, tmp_path):
        def fix(prompt, wd):
            (tmp_path / "src/main/java/Foo.java").write_text(
                "class Foo { }\n")
            return '{"verdict": "FIXED", "reason": "removed field"}'

        orch, _ = self._review_orch(tmp_path, fix)
        orch._agent.generate_triage.return_value = (
            '{"assessment": "APPROPRIATE", "confidence": 0.88, '
            '"reason": "minimal correct change"}'
        )
        orch._sonar.get_open_issues.side_effect = [[_make_issue("K1")], []]

        result = orch.handle_pr_premerge("o/r", 1, str(tmp_path))

        orch._agent.generate_triage.assert_called_once()  # reviewer
        orch._agent.build_fix_review_prompt.assert_called_once()
        assert result.fixes_verified == 1

    def test_reviewer_confidence_attached_to_fix(self, _sleep, tmp_path):
        def fix(prompt, wd):
            (tmp_path / "src/main/java/Foo.java").write_text(
                "class Foo { }\n")
            return "no json here"

        orch, _ = self._review_orch(tmp_path, fix)
        orch._agent.generate_triage.return_value = (
            '{"assessment": "INAPPROPRIATE", "confidence": 0.35, '
            '"reason": "breaks reflective access"}'
        )
        fixes, skipped = orch._triage_and_fix(
            [_make_issue("K1")], str(tmp_path))

        assert len(fixes) == 1 and not skipped
        assert fixes[0].fix_confidence == 0.35
        assert "INAPPROPRIATE" in fixes[0].explanation
        assert "breaks reflective access" in fixes[0].explanation

    def test_fp_escape_reviewed_and_skipped(self, _sleep, tmp_path):
        def fix(prompt, wd):
            return ('{"verdict": "FALSE_POSITIVE", '
                    '"reason": "field used via reflection"}')

        orch, _ = self._review_orch(tmp_path, fix)
        orch._agent.generate_triage.return_value = (
            '{"assessment": "AGREE_FALSE_POSITIVE", "confidence": 0.9, '
            '"reason": "reflection confirmed"}'
        )

        fixes, skipped = orch._triage_and_fix(
            [_make_issue("K1")], str(tmp_path))

        assert not fixes and len(skipped) == 1
        issue, triage = skipped[0]
        assert triage.verdict == "FALSE_POSITIVE"
        assert triage.confidence == 0.9
        assert "reflection" in triage.reason

    def test_fp_escape_with_reviewer_disagree_is_flagged(self, _sleep,
                                                         tmp_path):
        def fix(prompt, wd):
            return '{"verdict": "FALSE_POSITIVE", "reason": "looks fine"}'

        orch, _ = self._review_orch(tmp_path, fix)
        orch._agent.generate_triage.return_value = (
            '{"assessment": "DISAGREE", "confidence": 0.8, '
            '"reason": "this is a real leak"}'
        )

        fixes, skipped = orch._triage_and_fix(
            [_make_issue("K1")], str(tmp_path))

        assert len(skipped) == 1
        _, triage = skipped[0]
        assert "DISAGREES" in triage.reason
        assert "human review required" in triage.reason

    def test_no_change_no_verdict_is_failed_fix(self, _sleep, tmp_path):
        def fix(prompt, wd):
            return "I could not decide."

        orch, _ = self._review_orch(tmp_path, fix)

        fixes, skipped = orch._triage_and_fix(
            [_make_issue("K1")], str(tmp_path))

        assert not skipped and len(fixes) == 1
        assert fixes[0].success is False
        orch._agent.generate_triage.assert_not_called()

    def test_fix_review_prompt_receives_context_and_claim(self, _sleep,
                                                          tmp_path):
        def fix(prompt, wd):
            (tmp_path / "src/main/java/Foo.java").write_text(
                "class Foo { }\n")
            return '{"verdict": "FIXED", "reason": "removed field"}'

        orch, _ = self._review_orch(tmp_path, fix)
        orch._agent.generate_triage.return_value = (
            '{"assessment": "APPROPRIATE", "confidence": 0.9, "reason": "ok"}'
        )

        orch._triage_and_fix([_make_issue("K1")], str(tmp_path))

        kwargs = orch._agent.build_fix_review_prompt.call_args[1]
        # pre-fix content, captured before the agent edited the file
        assert kwargs["source_context"] == "class Foo { int bad; }\n"
        assert kwargs["fixer_claim"] == "removed field"
        assert kwargs["rule_how_to_fix"] == ""  # rule docs off by default

    def test_file_change_wins_over_fp_claim(self, _sleep, tmp_path):
        def fix(prompt, wd):
            (tmp_path / "src/main/java/Foo.java").write_text(
                "class Foo { }\n")
            return '{"verdict": "FALSE_POSITIVE", "reason": "but edited"}'

        orch, _ = self._review_orch(tmp_path, fix)
        orch._agent.generate_triage.return_value = (
            '{"assessment": "APPROPRIATE", "confidence": 0.7, "reason": "ok"}'
        )

        fixes, skipped = orch._triage_and_fix(
            [_make_issue("K1")], str(tmp_path))

        # the edit happened, so it is treated as a fix and reviewed
        assert len(fixes) == 1 and not skipped


@patch("src.orchestrator.time.sleep")
class TestTriageThenReview:
    """Option E: triage (pass 1) → fix TPs (pass 2) → review (pass 3)."""

    def _orch(self, tmp_path, fix_side_effect=None):
        config = _make_config(
            assessment=AssessmentConfig(strategy="triage_review"),
            pr_premerge=PrPremergeConfig(delivery="log"),
        )
        orch = _make_orchestrator(config)
        orch._sonar.run_scanner.return_value = True
        orch._sonar.get_quality_gate_status.return_value = "ERROR"
        orch._sonar.get_raw_source.return_value = ""
        orch._sonar.get_source_lines.return_value = ["line"]
        if fix_side_effect:
            orch._agent.generate_fix.side_effect = fix_side_effect
        return orch

    def test_false_positive_skips_fix_then_reviews(self, _sleep, tmp_path):
        orch = self._orch(tmp_path)
        orch._agent.generate_triage.side_effect = [
            '{"verdict": "FALSE_POSITIVE", "confidence": 0.9, "reason": "r"}',
            '{"assessment": "AGREE_FALSE_POSITIVE", "confidence": 0.8, '
            '"reason": "confirmed"}',
        ]

        fixes, skipped = orch._triage_and_fix(
            [_make_issue("K1")], str(tmp_path))

        orch._agent.generate_fix.assert_not_called()  # no pass 2 for FP
        assert not fixes and len(skipped) == 1
        _, triage = skipped[0]
        assert triage.verdict == "FALSE_POSITIVE"
        assert triage.confidence == 0.8  # reviewer's, not triage's

    def test_true_positive_fixes_then_reviews(self, _sleep, tmp_path):
        target = tmp_path / "src/main/java/Foo.java"
        target.parent.mkdir(parents=True)
        target.write_text("class Foo { int bad; }\n")

        def fix(prompt, wd):
            target.write_text("class Foo { }\n")
            return '{"fix_confidence": 0.9, "reason": "removed"}'

        orch = self._orch(tmp_path, fix_side_effect=fix)
        orch._agent.generate_triage.side_effect = [
            '{"verdict": "TRUE_POSITIVE", "confidence": 0.9, "reason": "r"}',
            '{"assessment": "APPROPRIATE", "confidence": 0.95, '
            '"reason": "good"}',
        ]

        fixes, skipped = orch._triage_and_fix(
            [_make_issue("K1")], str(tmp_path))

        assert not skipped and len(fixes) == 1
        assert fixes[0].success is True
        assert fixes[0].fix_confidence == 0.95  # reviewer's confidence
        orch._agent.build_fix_prompt.assert_called_once()
        orch._agent.build_fix_review_prompt.assert_called_once()

    def test_three_passes_invoked_for_true_positive(self, _sleep, tmp_path):
        target = tmp_path / "src/main/java/Foo.java"
        target.parent.mkdir(parents=True)
        target.write_text("class Foo { int bad; }\n")

        def fix(prompt, wd):
            target.write_text("class Foo { }\n")
            return "done"

        orch = self._orch(tmp_path, fix_side_effect=fix)
        orch._agent.generate_triage.side_effect = [
            '{"verdict": "TRUE_POSITIVE", "confidence": 0.9, "reason": "r"}',
            '{"assessment": "APPROPRIATE", "confidence": 0.9, "reason": "ok"}',
        ]

        orch._triage_and_fix([_make_issue("K1")], str(tmp_path))

        # pass 1 (triage) + pass 3 (review) on the judge, pass 2 on fixer
        assert orch._agent.generate_triage.call_count == 2
        assert orch._agent.generate_fix.call_count == 1


@patch("src.orchestrator.time.sleep")
class TestUsageReporting:

    def _usage_orch(self, judge_usage=None):
        config = _make_config(
            agent=AgentConfig(type="claude-code",
                              judge_type="bedrock-api"),
        )
        fixer, judge = MagicMock(), MagicMock()
        fixer.name.return_value = "Claude Code (sonnet)"
        judge.name.return_value = "Bedrock Converse (nova)"
        fixer.generate_fix.return_value = "fixed"
        fixer.get_usage.return_value = {
            "input_tokens": 1000, "output_tokens": 100, "cost_usd": 0.05,
        }
        judge.get_usage.return_value = judge_usage or {
            "input_tokens": 500, "output_tokens": 50, "cost_usd": 0.001,
        }
        with patch("src.orchestrator.AgentFactory") as mock_factory:
            mock_factory.create.side_effect = [fixer, judge]
            orch = SonarQubeOrchestrator(config)
        orch._sonar = MagicMock()
        orch._github = MagicMock()
        return orch

    def test_result_aggregates_fixer_and_judge_usage(self, _sleep):
        orch = self._usage_orch()
        orch._sonar.get_new_issues.return_value = []
        orch._sonar.get_quality_gate_status.return_value = "OK"

        usage = orch._collect_usage()
        assert usage["input_tokens"] == 1500
        assert usage["output_tokens"] == 150
        assert usage["cost_usd"] == pytest.approx(0.051)

    def test_unknown_component_cost_makes_total_none(self, _sleep):
        orch = self._usage_orch(judge_usage={
            "input_tokens": 500, "output_tokens": 50, "cost_usd": None,
        })
        usage = orch._collect_usage()
        assert usage["cost_usd"] is None
        assert usage["input_tokens"] == 1500

    def test_usage_summary_lists_roles_and_total(self, _sleep):
        orch = self._usage_orch()
        summary = orch._usage_summary()
        assert "fixer (Claude Code (sonnet))" in summary
        assert "judge (Bedrock Converse (nova))" in summary
        assert "$0.0510" in summary
        assert "1,500 in / 150 out" in summary

    def test_mode_result_carries_usage(self, _sleep):
        orch = self._usage_orch()
        orch._sonar.run_scanner.return_value = True
        orch._sonar.get_open_issues.side_effect = [[_make_issue("K1")], []]
        orch._sonar.get_quality_gate_status.return_value = "ERROR"
        orch._sonar.get_source_lines.return_value = ["line"]
        orch._judge.generate_triage.return_value = (
            '{"verdict": "TRUE_POSITIVE", "confidence": 0.9, "reason": "r"}'
        )

        result = orch.handle_pr_premerge("o/r", 1, "/tmp/proj")

        assert result.llm_input_tokens == 1500
        assert result.llm_output_tokens == 150
        assert result.llm_cost_usd == pytest.approx(0.051)

    def test_same_agent_not_double_counted(self, _sleep):
        orch = _make_orchestrator()  # judge is the fix agent
        orch._agent.get_usage.return_value = {
            "input_tokens": 100, "output_tokens": 10, "cost_usd": 0.01,
        }
        usage = orch._collect_usage()
        assert usage["input_tokens"] == 100


class TestSourceContextFallback:

    def test_falls_back_to_local_file_when_sonar_has_no_source(
            self, tmp_path):
        orch = _make_orchestrator(_make_config(
            assessment=AssessmentConfig(full_file_max_lines=0),
        ))
        orch._sonar.get_source_lines.return_value = []  # new file in PR
        target = tmp_path / "src/main/java/Foo.java"
        target.parent.mkdir(parents=True)
        target.write_text("\n".join(f"line{i}" for i in range(1, 21)))

        context = orch._get_source_context(_make_issue(line=10),
                                           str(tmp_path))

        assert "line5" in context and "line15" in context
        assert "line1\n" not in context  # window, not whole file

    def test_sonar_source_takes_precedence(self, tmp_path):
        orch = _make_orchestrator()
        orch._sonar.get_raw_source.return_value = ""
        orch._sonar.get_source_lines.return_value = ["from sonar"]

        context = orch._get_source_context(_make_issue(), str(tmp_path))

        assert context == "from sonar"

    def test_missing_local_file_returns_empty(self, tmp_path):
        orch = _make_orchestrator()
        orch._sonar.get_raw_source.return_value = ""
        orch._sonar.get_source_lines.return_value = []

        assert orch._get_source_context(_make_issue(), str(tmp_path)) == ""


class TestFullFileContext:

    def _write_file(self, tmp_path, n_lines):
        target = tmp_path / "src/main/java/Foo.java"
        target.parent.mkdir(parents=True)
        target.write_text("\n".join(f"line{i}" for i in range(1, n_lines + 1)))

    def test_small_file_uses_server_snapshot(self, tmp_path):
        orch = _make_orchestrator()  # default full_file_max_lines=150
        server_text = "\n".join(f"srv{i}" for i in range(1, 21))
        orch._sonar.get_raw_source.return_value = server_text
        self._write_file(tmp_path, 20)  # local differs from snapshot

        context = orch._get_source_context(_make_issue(line=10),
                                           str(tmp_path))

        assert context == server_text  # snapshot wins over local

    def test_small_file_falls_back_to_local(self, tmp_path):
        orch = _make_orchestrator()
        orch._sonar.get_raw_source.return_value = ""  # new file in PR
        self._write_file(tmp_path, 20)

        context = orch._get_source_context(_make_issue(line=10),
                                           str(tmp_path))

        assert context.startswith("line1\n")
        assert "line20" in context

    def test_large_file_uses_window(self, tmp_path):
        orch = _make_orchestrator(_make_config(
            assessment=AssessmentConfig(full_file_max_lines=10),
        ))
        orch._sonar.get_raw_source.return_value = ""
        orch._sonar.get_source_lines.return_value = ["from sonar"]
        self._write_file(tmp_path, 20)

        context = orch._get_source_context(_make_issue(line=10),
                                           str(tmp_path))

        assert context == "from sonar"


class TestRuleDocInjection:

    def _doc_orch(self, include=True):
        orch = _make_orchestrator(_make_config(
            assessment=AssessmentConfig(strategy="triage",
                                        include_rule_docs=include),
        ))
        orch._sonar.get_source_lines.return_value = ["line"]
        orch._sonar.get_rule_doc.return_value = {
            "how_to_fix": "use a logger",
            "exceptions": "literals under 5 chars are excluded",
        }
        return orch

    def test_judge_prompt_gets_exceptions(self):
        orch = self._doc_orch()
        orch._agent.generate_triage.return_value = (
            '{"verdict": "TRUE_POSITIVE", "confidence": 0.9, "reason": "r"}'
        )

        orch._triage_and_fix([_make_issue("K1")], "/tmp/proj")

        kwargs = orch._agent.build_triage_prompt.call_args[1]
        assert kwargs["rule_exceptions"] == (
            "literals under 5 chars are excluded")

    def test_fix_prompt_gets_how_to_fix(self):
        orch = self._doc_orch()
        orch._agent.generate_triage.return_value = (
            '{"verdict": "TRUE_POSITIVE", "confidence": 0.9, "reason": "r"}'
        )

        orch._triage_and_fix([_make_issue("K1")], "/tmp/proj")

        kwargs = orch._agent.build_fix_prompt.call_args[1]
        assert kwargs["rule_how_to_fix"] == "use a logger"

    def test_disabled_by_default_skips_rule_doc_fetch(self):
        orch = self._doc_orch(include=False)
        orch._agent.generate_triage.return_value = (
            '{"verdict": "TRUE_POSITIVE", "confidence": 0.9, "reason": "r"}'
        )

        orch._triage_and_fix([_make_issue("K1")], "/tmp/proj")

        orch._sonar.get_rule_doc.assert_not_called()
        kwargs = orch._agent.build_triage_prompt.call_args[1]
        assert kwargs["rule_exceptions"] == ""


class TestOrchestratorSummary:

    def test_get_project_summary(self):
        orch = _make_orchestrator()
        orch._sonar.get_measures.return_value = {
            "bugs": "3", "vulnerabilities": "5",
            "code_smells": "12", "coverage": "4.2",
            "duplicated_lines_density": "1.5", "ncloc": "350",
        }
        orch._sonar.get_quality_gate_status.return_value = "ERROR"
        orch._sonar.get_issue_count.return_value = 20

        summary = orch.get_project_summary()

        assert summary["bugs"] == "3"
        assert summary["vulnerabilities"] == "5"
        assert summary["quality_gate"] == "ERROR"
        assert summary["total_issues"] == 20


class TestGitHubClientFormatting:

    def test_format_issues_comment(self):
        issues = [
            _make_issue("K1", rule="java:S2259", severity="CRITICAL",
                        issue_type="BUG"),
            _make_issue("K2", rule="java:S3649", severity="BLOCKER",
                        issue_type="VULNERABILITY"),
        ]
        comment = GitHubClient.format_issues_comment(
            issues=issues,
            project_key="test-proj",
            sonar_url="http://sonar:9000",
        )
        assert "2 issue(s)" in comment
        assert "[CRITICAL]" in comment
        assert "[BLOCKER]" in comment
        assert "java:S2259" in comment
        assert "View in SonarQube" in comment

    def test_format_with_fix_summary(self):
        comment = GitHubClient.format_issues_comment(
            issues=[_make_issue()],
            project_key="p",
            sonar_url="http://x:9000",
            fix_summary="**1 fix(es)** generated",
        )
        assert "AI Fix Suggestions" in comment
        assert "1 fix(es)" in comment
