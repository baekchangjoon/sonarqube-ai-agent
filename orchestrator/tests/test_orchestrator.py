import pytest
from unittest.mock import MagicMock, patch

from src.agents.base import AgentType, FixResult
from src.config import (
    AgentConfig, AppConfig, NightlyBatchConfig, PostMergeConfig,
    PrPremergeConfig, ScannerConfig, SonarQubeConfig,
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
        mock_factory.create.return_value = mock_agent
        orch = SonarQubeOrchestrator(config or _make_config())
    orch._sonar = MagicMock()
    orch._github = MagicMock()
    return orch


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
