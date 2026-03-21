import pytest

from src.sonarqube_client import SonarIssue, SonarQubeClient
from src.config import SonarQubeConfig


class TestSonarIssue:

    def test_from_api_parses_all_fields(self):
        raw = {
            "key": "AXxyz",
            "rule": "java:S2259",
            "severity": "CRITICAL",
            "component": "myproject:src/main/java/Foo.java",
            "line": 42,
            "message": "A NullPointerException could be thrown",
            "type": "BUG",
            "effort": "15min",
        }
        issue = SonarIssue.from_api(raw)
        assert issue.key == "AXxyz"
        assert issue.rule == "java:S2259"
        assert issue.severity == "CRITICAL"
        assert issue.line == 42
        assert issue.issue_type == "BUG"
        assert issue.file_path == "src/main/java/Foo.java"

    def test_from_api_handles_missing_fields(self):
        raw = {"key": "minimal"}
        issue = SonarIssue.from_api(raw)
        assert issue.key == "minimal"
        assert issue.line == 0
        assert issue.message == ""

    def test_file_path_extraction(self):
        raw = {"key": "k", "component": "proj:src/pkg/File.java"}
        issue = SonarIssue.from_api(raw)
        assert issue.file_path == "src/pkg/File.java"


class TestSonarQubeClientUnit:
    """Unit tests using a mock SonarQube config (no live server needed)."""

    def test_init_sets_auth_header(self):
        config = SonarQubeConfig(
            url="http://fake:9000",
            token="test-token-123",
        )
        client = SonarQubeClient(config)
        auth = client._session.headers.get("Authorization")
        assert auth == "Bearer test-token-123"

    def test_is_healthy_returns_false_on_error(self):
        config = SonarQubeConfig(
            url="http://unreachable:9999",
            token="x",
        )
        client = SonarQubeClient(config)
        assert client.is_healthy() is False


@pytest.mark.integration
class TestSonarQubeClientIntegration:
    """Integration tests requiring a running SonarQube instance.

    Run with: pytest -m integration
    Requires: SonarQube at localhost:9000 with scanned project.
    """

    @pytest.fixture
    def client(self):
        import os
        url = os.environ.get("SONAR_URL", "http://localhost:9000")
        token = os.environ.get("SONAR_TOKEN", "")
        if not token:
            pytest.skip("SONAR_TOKEN not set")
        return SonarQubeClient(SonarQubeConfig(url=url, token=token))

    @pytest.fixture
    def project_key(self):
        import os
        return os.environ.get(
            "SONAR_PROJECT_KEY", "sonarqube-agent-test"
        )

    def test_is_healthy(self, client):
        assert client.is_healthy() is True

    def test_project_exists(self, client, project_key):
        assert client.project_exists(project_key) is True

    def test_get_open_issues_returns_list(self, client, project_key):
        issues = client.get_open_issues(project_key)
        assert isinstance(issues, list)
        assert len(issues) > 0

    def test_get_open_issues_filter_by_type(self, client, project_key):
        bugs = client.get_open_issues(
            project_key, issue_types=["BUG"]
        )
        assert all(i.issue_type == "BUG" for i in bugs)

    def test_get_open_issues_filter_by_severity(self, client, project_key):
        critical = client.get_open_issues(
            project_key, severities=["CRITICAL", "BLOCKER"]
        )
        assert all(
            i.severity in ("CRITICAL", "BLOCKER") for i in critical
        )

    def test_get_issue_count(self, client, project_key):
        count = client.get_issue_count(project_key)
        assert count > 0

    def test_get_quality_gate_status(self, client, project_key):
        status = client.get_quality_gate_status(project_key)
        assert status in ("OK", "WARN", "ERROR", "NONE")

    def test_get_measures(self, client, project_key):
        measures = client.get_measures(project_key)
        assert "bugs" in measures
        assert "vulnerabilities" in measures
        assert "code_smells" in measures

    def test_ephemeral_project_lifecycle(self, client):
        test_key = "integration-test-ephemeral-lifecycle"
        test_name = "Integration Test Ephemeral"

        created = client.create_project(test_key, test_name)
        assert created is True

        exists = client.project_exists(test_key)
        assert exists is True

        deleted = client.delete_project(test_key)
        assert deleted is True

        exists_after = client.project_exists(test_key)
        assert exists_after is False
