import logging
import time
from dataclasses import dataclass

from src.agents.base import FixResult, LLMAgent
from src.agents.factory import AgentFactory
from src.config import AppConfig
from src.github_client import GitHubClient
from src.sonarqube_client import SonarIssue, SonarQubeClient

logger = logging.getLogger(__name__)

SCAN_SETTLE_SECONDS = 8


@dataclass
class ModeResult:
    mode: str
    project_key: str
    issues_found: int
    fixes_attempted: int
    fixes_verified: int
    quality_gate: str


class SonarQubeOrchestrator:
    """Main orchestrator coordinating SonarQube analysis and AI-driven fixes.

    Implements three operational modes:
      Mode 1 — PR pre-merge: ephemeral project scan before merge
      Mode 2 — Post-merge:   main branch scan after merge
      Mode 3 — Nightly batch: scheduled legacy debt reduction
    """

    def __init__(self, config: AppConfig):
        self._config = config
        self._sonar = SonarQubeClient(config.sonarqube)
        self._agent: LLMAgent = AgentFactory.create(config.agent)
        self._github = GitHubClient()

        logger.info(
            "Orchestrator initialized (agent=%s, sonar=%s)",
            self._agent.name(), config.sonarqube.url,
        )

    @property
    def sonar(self) -> SonarQubeClient:
        return self._sonar

    @property
    def agent(self) -> LLMAgent:
        return self._agent

    # ── Mode 1: PR Pre-merge ────────────────

    def handle_pr_premerge(self, repo: str, pr_number: int,
                           project_dir: str) -> ModeResult:
        ephemeral_key = self._ephemeral_key(pr_number)
        pr_name = f"{self._config.sonarqube.main_project_key} [PR #{pr_number}]"
        logger.info("Mode 1: PR pre-merge analysis (PR #%d)", pr_number)

        scan_ok = self._scan_ephemeral(ephemeral_key, pr_name, project_dir)
        if not scan_ok:
            return ModeResult("pr_premerge", ephemeral_key, 0, 0, 0, "ERROR")

        issues, gate_status = self._fetch_issues_and_gate(ephemeral_key)
        fixes, verified = self._run_fixes(issues, project_dir)
        self._log_pr_comment(issues, ephemeral_key, verified)

        return self._build_result("pr_premerge", ephemeral_key,
                                  issues, fixes, verified, gate_status)

    def cleanup_pr_project(self, pr_number: int) -> bool:
        ephemeral_key = self._ephemeral_key(pr_number)
        return self._sonar.delete_project(ephemeral_key)

    # ── Mode 2: Post-merge ──────────────────

    def handle_post_merge(self,
                          project_dir: str = None) -> ModeResult:
        main_key = self._config.sonarqube.main_project_key
        logger.info("Mode 2: Post-merge analysis (%s)", main_key)

        self._optional_scan(project_dir, main_key)
        issues = self._sonar.get_new_issues(main_key)
        gate_status = self._sonar.get_quality_gate_status(main_key)

        logger.info("Post-merge: %d new issues, gate=%s", len(issues), gate_status)

        if not issues:
            return ModeResult("post_merge", main_key, 0, 0, 0, gate_status)

        fixes, verified = self._run_fixes(issues, project_dir or ".")
        return self._build_result("post_merge", main_key,
                                  issues, fixes, verified, gate_status)

    # ── Mode 3: Nightly Batch ───────────────

    def handle_nightly_batch(self,
                             project_dir: str = None) -> ModeResult:
        main_key = self._config.sonarqube.main_project_key
        batch_cfg = self._config.nightly_batch
        logger.info("Mode 3: Nightly batch (max=%d)", batch_cfg.max_issues_per_run)

        issues = self._sonar.get_open_issues(
            project_key=main_key,
            severities=batch_cfg.severity_filter,
            max_results=batch_cfg.max_issues_per_run,
        )
        gate_status = self._sonar.get_quality_gate_status(main_key)
        logger.info("Nightly batch: %d issues selected", len(issues))

        if not issues:
            return ModeResult("nightly_batch", main_key, 0, 0, 0, gate_status)

        fixes, verified = self._run_fixes(issues, project_dir or ".")
        return self._build_result("nightly_batch", main_key,
                                  issues, fixes, verified, gate_status)

    # ── Reporting ───────────────────────────

    def get_project_summary(self, project_key: str = None) -> dict:
        key = project_key or self._config.sonarqube.main_project_key
        measures = self._sonar.get_measures(key)
        gate = self._sonar.get_quality_gate_status(key)
        issue_count = self._sonar.get_issue_count(key)

        return {
            "project_key": key,
            "quality_gate": gate,
            "total_issues": issue_count,
            "bugs": measures.get("bugs", "0"),
            "vulnerabilities": measures.get("vulnerabilities", "0"),
            "code_smells": measures.get("code_smells", "0"),
            "coverage": measures.get("coverage", "0"),
            "duplicated_lines_density": measures.get(
                "duplicated_lines_density", "0"
            ),
            "ncloc": measures.get("ncloc", "0"),
        }

    # ── Private Helpers ─────────────────────

    def _ephemeral_key(self, pr_number: int) -> str:
        return self._config.scanner.ephemeral_key_pattern.format(
            project=self._config.sonarqube.main_project_key,
            pr_number=pr_number,
        )

    def _scan_ephemeral(self, key: str, name: str,
                        project_dir: str) -> bool:
        self._sonar.create_project(key, name)
        scan_ok = SonarQubeClient.run_scanner(
            project_dir=project_dir, project_key=key,
            sonar_url=self._config.sonarqube.url,
            sonar_token=self._config.sonarqube.token,
            project_name=name,
        )
        if not scan_ok:
            logger.error("Scanner failed for %s", key)
            return False
        time.sleep(SCAN_SETTLE_SECONDS)
        return True

    def _optional_scan(self, project_dir: str, project_key: str) -> None:
        if not project_dir:
            return
        SonarQubeClient.run_scanner(
            project_dir=project_dir, project_key=project_key,
            sonar_url=self._config.sonarqube.url,
            sonar_token=self._config.sonarqube.token,
        )
        time.sleep(SCAN_SETTLE_SECONDS)

    def _fetch_issues_and_gate(self, project_key: str):
        issues = self._sonar.get_open_issues(project_key)
        gate = self._sonar.get_quality_gate_status(project_key)
        logger.info("Scan result: %d issues, gate=%s", len(issues), gate)
        return issues, gate

    def _run_fixes(self, issues: list[SonarIssue],
                   working_dir: str):
        fixes = [self._generate_single_fix(i, working_dir) for i in issues]
        verified = [f for f in fixes if f.success]
        return fixes, verified

    def _generate_single_fix(self, issue: SonarIssue,
                             working_dir: str) -> FixResult:
        source_context = self._get_source_context(issue)
        prompt = self._agent.build_fix_prompt(
            issue_rule=issue.rule, issue_message=issue.message,
            file_path=issue.file_path, line=issue.line,
            source_context=source_context,
        )
        return self._invoke_agent(prompt, issue, source_context, working_dir)

    def _get_source_context(self, issue: SonarIssue) -> str:
        lines = self._sonar.get_source_lines(
            issue.component, max(1, issue.line - 5), issue.line + 5,
        )
        return "\n".join(lines) if lines else ""

    def _invoke_agent(self, prompt: str, issue: SonarIssue,
                      source_context: str, working_dir: str) -> FixResult:
        try:
            raw = self._agent.generate_fix(prompt, working_dir)
            if not raw:
                return _empty_fix(issue, source_context, "Empty response from agent")
            return FixResult(
                success=True, issue_key=issue.key,
                file_path=issue.file_path, original_code=source_context,
                fixed_code=raw, test_code="",
                explanation=f"Fix for {issue.rule}: {issue.message}",
            )
        except Exception as e:
            logger.error("Fix failed for %s: %s", issue.key, str(e))
            return _empty_fix(issue, source_context, str(e))

    def _log_pr_comment(self, issues, ephemeral_key, verified):
        comment = GitHubClient.format_issues_comment(
            issues=issues, project_key=ephemeral_key,
            sonar_url=self._config.sonarqube.url,
            fix_summary=_summarize_fixes(verified),
        )
        logger.info("PR comment generated (%d chars)", len(comment))

    @staticmethod
    def _build_result(mode, key, issues, fixes, verified, gate):
        return ModeResult(
            mode=mode, project_key=key,
            issues_found=len(issues), fixes_attempted=len(fixes),
            fixes_verified=len(verified), quality_gate=gate,
        )


def _empty_fix(issue: SonarIssue, source: str, error: str) -> FixResult:
    return FixResult(
        success=False, issue_key=issue.key, file_path=issue.file_path,
        original_code=source, fixed_code="", test_code="",
        errors=[error],
    )


def _summarize_fixes(fixes: list[FixResult]) -> str:
    if not fixes:
        return "No automated fixes were generated."
    lines = [f"**{len(fixes)} fix(es)** generated:\n"]
    for fix in fixes:
        status = "Verified" if fix.success else "Failed"
        lines.append(f"- `{fix.file_path}` — {fix.explanation} [{status}]")
    return "\n".join(lines)
