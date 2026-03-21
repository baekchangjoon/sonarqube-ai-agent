import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class AgentConfig:
    type: str = "claude-code"
    kiro: dict = field(default_factory=dict)
    claude: dict = field(default_factory=dict)
    gemini: dict = field(default_factory=dict)
    bedrock: dict = field(default_factory=dict)


@dataclass
class SonarQubeConfig:
    url: str = "http://localhost:9000"
    token: str = ""
    main_project_key: str = "sonarqube-agent-test"


@dataclass
class ScannerConfig:
    ephemeral_key_pattern: str = "{project}-pr-{pr_number}"


@dataclass
class ModeToggle:
    pr_premerge_enabled: bool = True
    post_merge_enabled: bool = True


@dataclass
class NightlyBatchConfig:
    enabled: bool = True
    max_issues_per_run: int = 10
    severity_filter: list = field(
        default_factory=lambda: ["BLOCKER", "CRITICAL", "MAJOR"]
    )


@dataclass
class AppConfig:
    agent: AgentConfig
    sonarqube: SonarQubeConfig
    scanner: ScannerConfig
    modes: ModeToggle
    nightly_batch: NightlyBatchConfig

    @staticmethod
    def load(config_path: str = None) -> "AppConfig":
        raw = _load_raw_yaml(config_path)
        modes_raw = raw.get("modes", {})
        return AppConfig(
            agent=_parse_agent(raw.get("agent", {})),
            sonarqube=_parse_sonarqube(raw.get("sonarqube", {})),
            scanner=_parse_scanner(raw.get("scanner", {})),
            modes=_parse_mode_toggles(modes_raw),
            nightly_batch=_parse_nightly(modes_raw),
        )


def _load_raw_yaml(config_path: str = None) -> dict:
    if config_path is None:
        config_path = str(Path(__file__).parent.parent / "config.yml")
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def _parse_agent(raw: dict) -> AgentConfig:
    return AgentConfig(
        type=raw.get("type", "claude-code"),
        kiro=raw.get("kiro", {}),
        claude=raw.get("claude", {}),
        gemini=raw.get("gemini", {}),
        bedrock=raw.get("bedrock", {}),
    )


def _parse_sonarqube(raw: dict) -> SonarQubeConfig:
    return SonarQubeConfig(
        url=_resolve_env(raw.get("url", "http://localhost:9000")),
        token=_resolve_env(raw.get("token", "")),
        main_project_key=raw.get("main_project_key", "sonarqube-agent-test"),
    )


def _parse_scanner(raw: dict) -> ScannerConfig:
    return ScannerConfig(
        ephemeral_key_pattern=raw.get(
            "ephemeral_key_pattern", "{project}-pr-{pr_number}"
        ),
    )


def _parse_mode_toggles(modes_raw: dict) -> ModeToggle:
    pr_raw = modes_raw.get("pr_premerge", {})
    pm_raw = modes_raw.get("post_merge", {})
    return ModeToggle(
        pr_premerge_enabled=pr_raw.get("enabled", True),
        post_merge_enabled=pm_raw.get("enabled", True),
    )


def _parse_nightly(modes_raw: dict) -> NightlyBatchConfig:
    raw = modes_raw.get("nightly_batch", {})
    return NightlyBatchConfig(
        enabled=raw.get("enabled", True),
        max_issues_per_run=raw.get("max_issues_per_run", 10),
        severity_filter=raw.get(
            "severity_filter", ["BLOCKER", "CRITICAL", "MAJOR"]
        ),
    )


def _resolve_env(value: str) -> str:
    """Replace ${VAR} placeholders with environment variable values."""
    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
        env_key = value[2:-1]
        return os.environ.get(env_key, "")
    return value
