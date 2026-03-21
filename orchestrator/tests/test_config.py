import os
import tempfile
from pathlib import Path

import pytest
import yaml

from src.config import AppConfig


class TestAppConfig:

    def test_load_default_config(self):
        config = AppConfig.load(
            str(Path(__file__).parent.parent / "config.yml")
        )
        assert config.agent.type == "claude-code"
        assert config.sonarqube.main_project_key == "sonarqube-agent-test"
        assert config.nightly_batch.max_issues_per_run == 10

    def test_load_custom_config(self, tmp_path):
        custom = {
            "agent": {"type": "gemini-cli"},
            "sonarqube": {
                "url": "http://custom:9000",
                "token": "abc123",
                "main_project_key": "custom-project",
            },
            "scanner": {
                "ephemeral_key_pattern": "{project}-pr-{pr_number}",
            },
            "modes": {
                "nightly_batch": {
                    "enabled": False,
                    "max_issues_per_run": 5,
                    "severity_filter": ["BLOCKER"],
                },
            },
        }
        config_path = tmp_path / "test-config.yml"
        config_path.write_text(yaml.dump(custom))

        config = AppConfig.load(str(config_path))
        assert config.agent.type == "gemini-cli"
        assert config.sonarqube.url == "http://custom:9000"
        assert config.sonarqube.token == "abc123"
        assert config.nightly_batch.max_issues_per_run == 5
        assert config.nightly_batch.severity_filter == ["BLOCKER"]

    def test_env_variable_resolution(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TEST_SONAR_URL", "http://env-resolved:9000")
        monkeypatch.setenv("TEST_SONAR_TOKEN", "env-token-xyz")

        custom = {
            "agent": {"type": "kiro-cli"},
            "sonarqube": {
                "url": "${TEST_SONAR_URL}",
                "token": "${TEST_SONAR_TOKEN}",
                "main_project_key": "test",
            },
            "scanner": {},
            "modes": {},
        }
        config_path = tmp_path / "env-config.yml"
        config_path.write_text(yaml.dump(custom))

        config = AppConfig.load(str(config_path))
        assert config.sonarqube.url == "http://env-resolved:9000"
        assert config.sonarqube.token == "env-token-xyz"

    def test_ephemeral_key_pattern(self):
        config = AppConfig.load(
            str(Path(__file__).parent.parent / "config.yml")
        )
        key = config.scanner.ephemeral_key_pattern.format(
            project="myproj", pr_number=42
        )
        assert key == "myproj-pr-42"
