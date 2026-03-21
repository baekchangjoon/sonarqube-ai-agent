import pytest
from unittest.mock import MagicMock, patch

from src.agents.base import AgentType, FixResult
from src.config import (
    AgentConfig, AppConfig, ModeToggle, NightlyBatchConfig,
    ScannerConfig, SonarQubeConfig,
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
        "modes": ModeToggle(),
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


class TestOrchestratorEphemeralKey:

    def test_ephemeral_key_format(self):
        config = _make_config()
        with patch.object(SonarQubeOrchestrator, "__init__", lambda s, c: None):
            orch = SonarQubeOrchestrator.__new__(SonarQubeOrchestrator)
            orch._config = config
        key = orch._ephemeral_key(42)
        assert key == "test-project-pr-42"


class TestOrchestratorPostMerge:

    @patch("src.orchestrator.AgentFactory")
    def test_post_merge_no_issues(self, mock_factory):
        mock_agent = MagicMock()
        mock_agent.name.return_value = "Mock Agent"
        mock_factory.create.return_value = mock_agent

        config = _make_config()
        orch = SonarQubeOrchestrator(config)
        orch._sonar = MagicMock()
        orch._sonar.get_new_issues.return_value = []
        orch._sonar.get_quality_gate_status.return_value = "OK"

        result = orch.handle_post_merge()

        assert result.mode == "post_merge"
        assert result.issues_found == 0
        assert result.quality_gate == "OK"
        mock_agent.generate_fix.assert_not_called()

    @patch("src.orchestrator.AgentFactory")
    def test_post_merge_with_issues_triggers_fixes(self, mock_factory):
        mock_agent = MagicMock()
        mock_agent.name.return_value = "Mock Agent"
        mock_agent.generate_fix.return_value = "fixed code"
        mock_agent.build_fix_prompt.return_value = "prompt"
        mock_factory.create.return_value = mock_agent

        config = _make_config()
        orch = SonarQubeOrchestrator(config)
        orch._sonar = MagicMock()
        orch._sonar.get_new_issues.return_value = [
            _make_issue("K1"), _make_issue("K2"),
        ]
        orch._sonar.get_quality_gate_status.return_value = "ERROR"
        orch._sonar.get_source_lines.return_value = ["line1", "line2"]

        result = orch.handle_post_merge()

        assert result.issues_found == 2
        assert result.fixes_attempted == 2
        assert result.quality_gate == "ERROR"


class TestOrchestratorNightlyBatch:

    @patch("src.orchestrator.AgentFactory")
    def test_nightly_batch_respects_severity_filter(self, mock_factory):
        mock_agent = MagicMock()
        mock_agent.name.return_value = "Mock Agent"
        mock_factory.create.return_value = mock_agent

        config = _make_config(
            nightly_batch=NightlyBatchConfig(
                severity_filter=["BLOCKER"],
                max_issues_per_run=5,
            ),
        )
        orch = SonarQubeOrchestrator(config)
        orch._sonar = MagicMock()
        orch._sonar.get_open_issues.return_value = []
        orch._sonar.get_quality_gate_status.return_value = "OK"

        orch.handle_nightly_batch()

        orch._sonar.get_open_issues.assert_called_once_with(
            project_key="test-project",
            severities=["BLOCKER"],
            max_results=5,
        )


class TestOrchestratorSummary:

    @patch("src.orchestrator.AgentFactory")
    def test_get_project_summary(self, mock_factory):
        mock_agent = MagicMock()
        mock_agent.name.return_value = "Mock"
        mock_factory.create.return_value = mock_agent

        config = _make_config()
        orch = SonarQubeOrchestrator(config)
        orch._sonar = MagicMock()
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
