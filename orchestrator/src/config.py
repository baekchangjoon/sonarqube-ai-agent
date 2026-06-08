import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class AgentConfig:
    type: str = "claude-code"
    # Judge role (FP triage, fix review) — judgment calls need no
    # file-editing harness, so any backend works (e.g. bedrock-api).
    # Defaults to the fix agent's type/model when unset.
    judge_type: str = ""
    judge_model: str = ""
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
    # Analysis paths (defaults = Maven standard layout). Empty string
    # omits the corresponding -D flag (e.g. no test root).
    sources: str = "src/main/java"
    tests: str = "src/test/java"
    java_binaries: str = "target/classes"
    java_test_binaries: str = "target/test-classes"

    def paths(self) -> dict:
        return {
            "sources": self.sources,
            "tests": self.tests,
            "java_binaries": self.java_binaries,
            "java_test_binaries": self.java_test_binaries,
        }


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
    #   "none":          fix every issue, no screening
    #   "triage":        pre-fix LLM judgment; FALSE_POSITIVE → skip (C)
    #   "review":        fix-with-FP-escape, then an independent LLM call
    #                    assesses the fix or the FP claim (D)
    #   "triage_review": judge triages first (FP→skip), fixer fixes only
    #                    true positives, judge then reviews each outcome (E)
    strategy: str = "none"
    # Source lines shown around the issue line in triage/fix prompts.
    # 5 keeps prompts small but can cut off class-level Javadoc; larger
    # values give harness-less judges more of the surrounding intent.
    context_lines: int = 5
    # Files at most this many lines are injected whole instead of as a
    # window — full intent for free on small files (0 = always window).
    full_file_max_lines: int = 150
    # Inject SonarQube rule docs into prompts: the how-to-fix section
    # for the fixer, the documented exceptions for the judge.
    include_rule_docs: bool = False


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
        # ./config.yml (installed CLI usage) > repo default
        candidates = [Path.cwd() / "config.yml",
                      Path(__file__).parent.parent / "config.yml"]
        existing = [p for p in candidates if p.exists()]
        if not existing:
            raise FileNotFoundError(
                "config.yml not found in the current directory — "
                "pass one with --config <path>"
            )
        config_path = str(existing[0])
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def _parse_agent(raw: dict) -> AgentConfig:
    return AgentConfig(
        type=raw.get("type", "claude-code"),
        judge_type=raw.get("judge_type", ""),
        judge_model=raw.get("judge_model", ""),
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
        sources=raw.get("sources", "src/main/java"),
        tests=raw.get("tests", "src/test/java"),
        java_binaries=raw.get("java_binaries", "target/classes"),
        java_test_binaries=raw.get("java_test_binaries",
                                   "target/test-classes"),
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
    if strategy not in ("none", "triage", "review", "triage_review"):
        raise ValueError(
            f"assessment.strategy must be 'none', 'triage', 'review' or "
            f"'triage_review', got: {strategy}"
        )
    return AssessmentConfig(
        strategy=strategy,
        context_lines=int((raw or {}).get("context_lines", 5)),
        full_file_max_lines=int(
            (raw or {}).get("full_file_max_lines", 150)
        ),
        include_rule_docs=bool(
            (raw or {}).get("include_rule_docs", False)
        ),
    )


def _resolve_env(value: str) -> str:
    """Replace ${VAR} placeholders with environment variable values."""
    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
        env_key = value[2:-1]
        return os.environ.get(env_key, "")
    return value
