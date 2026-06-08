import pytest

from src.sonarqube_client import (
    SonarIssue, SonarQubeClient, _build_scanner_cmd, _docker_reachable_url,
)
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


class TestRuleDoc:

    def _client(self, rule_payload):
        from unittest.mock import MagicMock
        client = SonarQubeClient(SonarQubeConfig(url="http://x", token="t"))
        client._get = MagicMock(return_value={"rule": rule_payload})
        return client

    def test_extracts_how_to_fix_and_exceptions(self):
        client = self._client({
            "descriptionSections": [
                {"key": "how_to_fix",
                 "content": "<p>Use <code>constants</code>.</p>"},
                {"key": "root_cause",
                 "content": "<p>Dups are bad.</p>"
                            "<h3>Exceptions</h3>"
                            "<p>Literals under 5 chars are excluded.</p>"},
            ],
        })
        doc = client.get_rule_doc("java:S1192")
        assert doc["how_to_fix"] == "Use constants."
        assert doc["exceptions"] == "Literals under 5 chars are excluded."

    def test_missing_sections_yield_empty(self):
        client = self._client({
            "descriptionSections": [
                {"key": "root_cause", "content": "<p>No exceptions here.</p>"},
            ],
        })
        doc = client.get_rule_doc("java:S106")
        assert doc == {"how_to_fix": "", "exceptions": ""}

    def test_legacy_html_desc_fallback(self):
        client = self._client({
            "htmlDesc": "<p>Old format.</p><h3>Exceptions</h3>"
                        "<p>volatile flags are fine.</p><h3>See</h3>x",
        })
        doc = client.get_rule_doc("java:S2142")
        assert doc["exceptions"] == "volatile flags are fine."

    def test_cached_per_rule_key(self):
        client = self._client({"descriptionSections": []})
        client.get_rule_doc("java:S1")
        client.get_rule_doc("java:S1")
        assert client._get.call_count == 1

    def test_fetch_error_returns_empty(self):
        from unittest.mock import MagicMock
        client = SonarQubeClient(SonarQubeConfig(url="http://x", token="t"))
        client._get = MagicMock(side_effect=Exception("boom"))
        assert client.get_rule_doc("java:S1") == {
            "how_to_fix": "", "exceptions": "",
        }

    def test_entity_encoded_markup_is_stripped_not_revived(self):
        # unescape-then-strip: an entity-encoded tag must not survive as
        # live markup in the prompt.
        client = self._client({
            "descriptionSections": [
                {"key": "how_to_fix",
                 "content": "&lt;script&gt;alert(1)&lt;/script&gt;ok"},
            ],
        })
        doc = client.get_rule_doc("java:S1")
        assert "<script>" not in doc["how_to_fix"]
        assert doc["how_to_fix"] == "alert(1)ok"

    def test_control_chars_stripped(self):
        client = self._client({
            "descriptionSections": [
                {"key": "how_to_fix", "content": "a\x00b\x07c\tok\nline"},
            ],
        })
        doc = client.get_rule_doc("java:S1")
        assert doc["how_to_fix"] == "abc\tok\nline"

    def test_length_capped(self):
        client = self._client({
            "descriptionSections": [
                {"key": "how_to_fix", "content": "x" * 9000},
            ],
        })
        doc = client.get_rule_doc("java:S1")
        assert len(doc["how_to_fix"]) == 4000


class TestScannerCommand:

    def test_remote_url_passes_through(self):
        assert (_docker_reachable_url("https://sonar.example.com")
                == "https://sonar.example.com")

    def test_localhost_is_mapped_for_docker(self):
        mapped = _docker_reachable_url("http://localhost:9000")
        assert "localhost" not in mapped
        assert mapped.endswith(":9000")

    def test_extra_args_appended(self):
        cmd = _build_scanner_cmd(
            project_dir="/tmp/p", project_key="k",
            sonar_url="https://sonar.example.com", sonar_token="t",
            extra_args=["-Dsonar.pullrequest.key=7"],
        )
        assert cmd[-1] == "-Dsonar.pullrequest.key=7"
        assert "SONAR_HOST_URL=https://sonar.example.com" in cmd

    def test_no_extra_args_uses_maven_layout_defaults(self):
        cmd = _build_scanner_cmd(
            project_dir="/tmp/p", project_key="k",
            sonar_url="https://sonar.example.com", sonar_token="t",
        )
        assert "-Dsonar.sources=src/main/java" in cmd
        assert "-Dsonar.tests=src/test/java" in cmd
        assert "-Dsonar.java.binaries=target/classes" in cmd

    def test_paths_override(self):
        cmd = _build_scanner_cmd(
            project_dir="/tmp/p", project_key="k",
            sonar_url="https://sonar.example.com", sonar_token="t",
            paths={"sources": "lib", "tests": "",
                   "java_binaries": "out", "java_test_binaries": ""},
        )
        assert "-Dsonar.sources=lib" in cmd
        assert "-Dsonar.java.binaries=out" in cmd
        # empty values omit the flags entirely
        assert not any(a.startswith("-Dsonar.tests=") for a in cmd)
        assert not any(a.startswith("-Dsonar.java.test.binaries=")
                       for a in cmd)


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
