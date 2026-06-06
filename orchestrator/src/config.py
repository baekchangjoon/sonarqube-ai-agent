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
    # "ephemeral": CE workaround — temp project per PR
    # "native":    sonar.pullrequest.* params (requires branch/PR plugin)
    pr_mode: str = "ephemeral"
    # Shell command run in project_dir before each scan (e.g. maven build).
    # Empty = skip.
    rebuild_command: str = ""


@dataclass
class PrPremergeConfig:
    enabled: bool = True
    delivery: str = "comment"  # "comment": gh pr comment, "log": log only
    max_issues_per_run: int = 0  # 0 = unlimited
    # Push verified fixes as a new commit to the PR branch
    # (project_dir must be a git checkout of that branch)
    push_fix_commit: bool = False


@dataclass
class PostMergeConfig:
    enabled: bool = True
    max_issues_per_run: int = 0
    create_fix_pr: bool = False
    fix_pr_repo: str = ""  # owner/repo — required when create_fix_pr=true
    fix_pr_base: str = "main"


@dataclass
class NightlyBatchConfig:
    enabled: bool = True
    max_issues_per_run: int = 10
    severity_filter: list = field(
        default_factory=lambda: ["BLOCKER", "CRITICAL", "MAJOR"]
    )
    create_fix_pr: bool = False
    fix_pr_repo: str = ""  # owner/repo — required when create_fix_pr=true
    fix_pr_base: str = "main"


@dataclass
class AssessmentConfig:
    # False-positive / fix-quality assessment strategy:
    #   "none":   fix every issue, no screening
    #   "triage": pre-fix LLM judgment; FALSE_POSITIVE → skip + report (C)
    #   "review": fix-with-FP-escape, then an independent LLM call
    #             assesses the fix or the FP claim (D)
    strategy: str = "none"


@dataclass
class AppConfig:
    agent: AgentConfig
    sonarqube: SonarQubeConfig
    scanner: ScannerConfig
    pr_premerge: PrPremergeConfig
    post_merge: PostMergeConfig
    nightly_batch: NightlyBatchConfig
    assessment: AssessmentConfig = field(default_factory=AssessmentConfig)

    @staticmethod
    def load(config_path: str = None) -> "AppConfig":
        raw = _load_raw_yaml(config_path)
        modes_raw = raw.get("modes", {})
        return AppConfig(
            agent=_parse_agent(raw.get("agent", {})),
            sonarqube=_parse_sonarqube(raw.get("sonarqube", {})),
            scanner=_parse_scanner(raw.get("scanner", {})),
            pr_premerge=_parse_pr_premerge(modes_raw),
            post_merge=_parse_post_merge(modes_raw),
            nightly_batch=_parse_nightly(modes_raw),
            assessment=_parse_assessment(raw.get("assessment", {})),
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
    pr_mode = raw.get("pr_mode", "ephemeral")
    if pr_mode not in ("ephemeral", "native"):
        raise ValueError(
            f"scanner.pr_mode must be 'ephemeral' or 'native', got: {pr_mode}"
        )
    return ScannerConfig(
        ephemeral_key_pattern=raw.get(
            "ephemeral_key_pattern", "{project}-pr-{pr_number}"
        ),
        pr_mode=pr_mode,
        rebuild_command=raw.get("rebuild_command", ""),
    )


def _parse_pr_premerge(modes_raw: dict) -> PrPremergeConfig:
    raw = modes_raw.get("pr_premerge", {})
    return PrPremergeConfig(
        enabled=raw.get("enabled", True),
        delivery=raw.get("delivery", "comment"),
        max_issues_per_run=raw.get("max_issues_per_run", 0),
        push_fix_commit=raw.get("push_fix_commit", False),
    )


def _parse_post_merge(modes_raw: dict) -> PostMergeConfig:
    raw = modes_raw.get("post_merge", {})
    fix_pr_raw = raw.get("fix_pr", {})
    return PostMergeConfig(
        enabled=raw.get("enabled", True),
        max_issues_per_run=raw.get("max_issues_per_run", 0),
        create_fix_pr=raw.get("create_fix_pr", False),
        fix_pr_repo=fix_pr_raw.get("repo", ""),
        fix_pr_base=fix_pr_raw.get("base", "main"),
    )


def _parse_nightly(modes_raw: dict) -> NightlyBatchConfig:
    raw = modes_raw.get("nightly_batch", {})
    fix_pr_raw = raw.get("fix_pr", {})
    return NightlyBatchConfig(
        enabled=raw.get("enabled", True),
        max_issues_per_run=raw.get("max_issues_per_run", 10),
        severity_filter=raw.get(
            "severity_filter", ["BLOCKER", "CRITICAL", "MAJOR"]
        ),
        create_fix_pr=raw.get("create_fix_pr", False),
        fix_pr_repo=fix_pr_raw.get("repo", ""),
        fix_pr_base=fix_pr_raw.get("base", "main"),
    )


def _parse_assessment(raw: dict) -> AssessmentConfig:
    strategy = (raw or {}).get("strategy", "none")
    if strategy not in ("none", "triage", "review"):
        raise ValueError(
            f"assessment.strategy must be 'none', 'triage' or 'review', "
            f"got: {strategy}"
        )
    return AssessmentConfig(strategy=strategy)


def _resolve_env(value: str) -> str:
    """Replace ${VAR} placeholders with environment variable values."""
    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
        env_key = value[2:-1]
        return os.environ.get(env_key, "")
    return value
