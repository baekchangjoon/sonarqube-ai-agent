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

    def test_pr_mode_defaults_to_ephemeral(self, tmp_path):
        config_path = tmp_path / "c.yml"
        config_path.write_text(yaml.dump({"scanner": {}}))
        config = AppConfig.load(str(config_path))
        assert config.scanner.pr_mode == "ephemeral"

    def test_pr_mode_native(self, tmp_path):
        config_path = tmp_path / "c.yml"
        config_path.write_text(yaml.dump({"scanner": {"pr_mode": "native"}}))
        config = AppConfig.load(str(config_path))
        assert config.scanner.pr_mode == "native"

    def test_invalid_pr_mode_raises(self, tmp_path):
        config_path = tmp_path / "c.yml"
        config_path.write_text(yaml.dump({"scanner": {"pr_mode": "bogus"}}))
        with pytest.raises(ValueError):
            AppConfig.load(str(config_path))

    def test_mode_configs_defaults(self, tmp_path):
        config_path = tmp_path / "c.yml"
        config_path.write_text(yaml.dump({}))
        config = AppConfig.load(str(config_path))
        assert config.pr_premerge.enabled is True
        assert config.pr_premerge.delivery == "comment"
        assert config.pr_premerge.max_issues_per_run == 0
        assert config.pr_premerge.push_fix_commit is False
        assert config.post_merge.enabled is True
        assert config.post_merge.create_fix_pr is False
        assert config.nightly_batch.create_fix_pr is False
        assert config.nightly_batch.fix_pr_base == "main"

    def test_judge_defaults_empty(self, tmp_path):
        config_path = tmp_path / "c.yml"
        config_path.write_text(yaml.dump({}))
        config = AppConfig.load(str(config_path))
        assert config.agent.judge_type == ""
        assert config.agent.judge_model == ""

    def test_judge_overrides(self, tmp_path):
        custom = {
            "agent": {
                "type": "claude-code",
                "judge_type": "bedrock-api",
                "judge_model": "global.anthropic.claude-opus-4-6",
            },
        }
        config_path = tmp_path / "c.yml"
        config_path.write_text(yaml.dump(custom))
        config = AppConfig.load(str(config_path))
        assert config.agent.judge_type == "bedrock-api"
        assert config.agent.judge_model == "global.anthropic.claude-opus-4-6"

    def test_assessment_default_none(self, tmp_path):
        config_path = tmp_path / "c.yml"
        config_path.write_text(yaml.dump({}))
        config = AppConfig.load(str(config_path))
        assert config.assessment.strategy == "none"

    @pytest.mark.parametrize("strategy", ["none", "triage", "review"])
    def test_assessment_strategies(self, tmp_path, strategy):
        config_path = tmp_path / "c.yml"
        config_path.write_text(
            yaml.dump({"assessment": {"strategy": strategy}})
        )
        config = AppConfig.load(str(config_path))
        assert config.assessment.strategy == strategy

    def test_invalid_assessment_strategy_raises(self, tmp_path):
        config_path = tmp_path / "c.yml"
        config_path.write_text(
            yaml.dump({"assessment": {"strategy": "bogus"}})
        )
        with pytest.raises(ValueError):
            AppConfig.load(str(config_path))

    def test_pr_premerge_push_fix_commit(self, tmp_path):
        custom = {
            "modes": {"pr_premerge": {"push_fix_commit": True}},
        }
        config_path = tmp_path / "c.yml"
        config_path.write_text(yaml.dump(custom))
        config = AppConfig.load(str(config_path))
        assert config.pr_premerge.push_fix_commit is True

    def test_post_merge_fix_pr_config(self, tmp_path):
        custom = {
            "modes": {
                "post_merge": {
                    "create_fix_pr": True,
                    "fix_pr": {"repo": "owner/repo", "base": "develop"},
                },
            },
        }
        config_path = tmp_path / "c.yml"
        config_path.write_text(yaml.dump(custom))
        config = AppConfig.load(str(config_path))
        assert config.post_merge.create_fix_pr is True
        assert config.post_merge.fix_pr_repo == "owner/repo"
        assert config.post_merge.fix_pr_base == "develop"

    def test_nightly_fix_pr_config(self, tmp_path):
        custom = {
            "modes": {
                "nightly_batch": {
                    "create_fix_pr": True,
                    "fix_pr": {"repo": "owner/repo", "base": "develop"},
                },
            },
        }
        config_path = tmp_path / "c.yml"
        config_path.write_text(yaml.dump(custom))
        config = AppConfig.load(str(config_path))
        assert config.nightly_batch.create_fix_pr is True
        assert config.nightly_batch.fix_pr_repo == "owner/repo"
        assert config.nightly_batch.fix_pr_base == "develop"
