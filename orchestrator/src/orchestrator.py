import logging
import subprocess
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
      Mode 1 — PR pre-merge: PR scan (ephemeral project or native
               sonar.pullrequest.*) + fix + verification + PR comment
      Mode 2 — Post-merge:   main branch scan after merge + fix + verification
      Mode 3 — Nightly batch: scheduled legacy debt reduction + optional Fix PR

    A fix counts as *verified* only when a re-scan after the fix shows
    the original issue is no longer open.
    """

    def __init__(self, config: AppConfig):
        self._config = config
        self._sonar = SonarQubeClient(config.sonarqube)
        self._agent: LLMAgent = AgentFactory.create(config.agent)
        self._github = GitHubClient()

        logger.info(
            "Orchestrator initialized (agent=%s, sonar=%s, pr_mode=%s)",
            self._agent.name(), config.sonarqube.url, config.scanner.pr_mode,
        )

    @property
    def sonar(self) -> SonarQubeClient:
        return self._sonar

    @property
    def agent(self) -> LLMAgent:
        return self._agent

    # ── Mode 1: PR Pre-merge ────────────────

    def handle_pr_premerge(self, repo: str, pr_number: int,
                           project_dir: str,
                           pr_branch: str = None,
                           pr_base: str = "main") -> ModeResult:
        if not self._config.pr_premerge.enabled:
            return self._disabled("pr_premerge")

        if self._config.scanner.pr_mode == "native":
            return self._pr_premerge_native(
                repo, pr_number, project_dir, pr_branch, pr_base
            )
        return self._pr_premerge_ephemeral(repo, pr_number, project_dir)

    def _pr_premerge_ephemeral(self, repo: str, pr_number: int,
                               project_dir: str) -> ModeResult:
        ephemeral_key = self._ephemeral_key(pr_number)
        pr_name = f"{self._config.sonarqube.main_project_key} [PR #{pr_number}]"
        logger.info("Mode 1: PR pre-merge, ephemeral project (PR #%d)", pr_number)

        self._sonar.create_project(ephemeral_key, pr_name)
        if not self._build_and_scan(project_dir, ephemeral_key,
                                    project_name=pr_name):
            return ModeResult("pr_premerge", ephemeral_key, 0, 0, 0, "ERROR")

        issues = self._sonar.get_open_issues(ephemeral_key)
        gate = self._sonar.get_quality_gate_status(ephemeral_key)
        logger.info("Scan result: %d issues, gate=%s", len(issues), gate)
        issues = _limit(issues, self._config.pr_premerge.max_issues_per_run)

        fixes, verified = self._fix_and_verify(
            issues, project_dir, ephemeral_key, scan_project_name=pr_name,
        )
        self._deliver_pr_comment(repo, pr_number, issues,
                                 ephemeral_key, verified)
        return self._build_result("pr_premerge", ephemeral_key,
                                  issues, fixes, verified, gate)

    def _pr_premerge_native(self, repo: str, pr_number: int,
                            project_dir: str, pr_branch: str,
                            pr_base: str) -> ModeResult:
        main_key = self._config.sonarqube.main_project_key
        pr_key = str(pr_number)
        logger.info("Mode 1: PR pre-merge, native PR analysis (PR #%d)",
                    pr_number)

        extra_args = [
            f"-Dsonar.pullrequest.key={pr_key}",
            f"-Dsonar.pullrequest.branch={pr_branch or f'pr-{pr_number}'}",
            f"-Dsonar.pullrequest.base={pr_base}",
        ]
        if not self._build_and_scan(project_dir, main_key,
                                    extra_args=extra_args):
            return ModeResult("pr_premerge", main_key, 0, 0, 0, "ERROR")

        issues = self._sonar.get_open_issues(main_key, pull_request=pr_key)
        gate = self._sonar.get_quality_gate_status(main_key,
                                                   pull_request=pr_key)
        logger.info("Scan result: %d issues, gate=%s", len(issues), gate)
        issues = _limit(issues, self._config.pr_premerge.max_issues_per_run)

        fixes, verified = self._fix_and_verify(
            issues, project_dir, main_key,
            pull_request=pr_key, scan_extra_args=extra_args,
        )
        self._deliver_pr_comment(repo, pr_number, issues, main_key, verified)
        return self._build_result("pr_premerge", main_key,
                                  issues, fixes, verified, gate)

    def cleanup_pr_project(self, pr_number: int) -> bool:
        if self._config.scanner.pr_mode == "native":
            return True  # no ephemeral project to delete
        return self._sonar.delete_project(self._ephemeral_key(pr_number))

    # ── Mode 2: Post-merge ──────────────────

    def handle_post_merge(self,
                          project_dir: str = None) -> ModeResult:
        if not self._config.post_merge.enabled:
            return self._disabled("post_merge")

        main_key = self._config.sonarqube.main_project_key
        logger.info("Mode 2: Post-merge analysis (%s)", main_key)

        if project_dir:
            self._build_and_scan(project_dir, main_key)
        issues = self._sonar.get_new_issues(main_key)
        gate = self._sonar.get_quality_gate_status(main_key)
        logger.info("Post-merge: %d new issues, gate=%s", len(issues), gate)

        if not issues:
            return ModeResult("post_merge", main_key, 0, 0, 0, gate)
        issues = _limit(issues, self._config.post_merge.max_issues_per_run)

        fixes, verified = self._fix_with_optional_verify(
            issues, project_dir, main_key,
        )
        return self._build_result("post_merge", main_key,
                                  issues, fixes, verified, gate)

    # ── Mode 3: Nightly Batch ───────────────

    def handle_nightly_batch(self,
                             project_dir: str = None) -> ModeResult:
        batch_cfg = self._config.nightly_batch
        if not batch_cfg.enabled:
            return self._disabled("nightly_batch")

        main_key = self._config.sonarqube.main_project_key
        logger.info("Mode 3: Nightly batch (max=%d)",
                    batch_cfg.max_issues_per_run)

        issues = self._sonar.get_open_issues(
            project_key=main_key,
            severities=batch_cfg.severity_filter,
            max_results=batch_cfg.max_issues_per_run,
        )
        gate = self._sonar.get_quality_gate_status(main_key)
        logger.info("Nightly batch: %d issues selected", len(issues))

        if not issues:
            return ModeResult("nightly_batch", main_key, 0, 0, 0, gate)

        fixes, verified = self._fix_with_optional_verify(
            issues, project_dir, main_key,
        )
        if batch_cfg.create_fix_pr and verified:
            self._create_nightly_fix_pr(project_dir, verified, batch_cfg)
        return self._build_result("nightly_batch", main_key,
                                  issues, fixes, verified, gate)

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

    # ── Fix + Verification ──────────────────

    def _fix_and_verify(self, issues: list[SonarIssue], project_dir: str,
                        project_key: str, pull_request: str = None,
                        scan_extra_args: list = None,
                        scan_project_name: str = None):
        """Run fixes, then re-scan and count an issue as verified only
        if it is no longer open."""
        fixes = self._run_fixes(issues, project_dir)
        if not any(f.success for f in fixes):
            return fixes, []

        if not self._build_and_scan(project_dir, project_key,
                                    project_name=scan_project_name,
                                    extra_args=scan_extra_args):
            logger.warning("Verification re-scan failed — fixes unverified")
            return fixes, []

        still_open = {
            i.key for i in self._sonar.get_open_issues(
                project_key, max_results=500, pull_request=pull_request,
            )
        }
        verified = [f for f in fixes
                    if f.success and f.issue_key not in still_open]
        logger.info("Verification: %d/%d fixes confirmed by re-scan",
                    len(verified), len(fixes))
        return fixes, verified

    def _fix_with_optional_verify(self, issues, project_dir, project_key):
        if project_dir:
            return self._fix_and_verify(issues, project_dir, project_key)
        logger.warning("No --project-dir given — fixes cannot be "
                       "applied locally or verified")
        fixes = self._run_fixes(issues, ".")
        return fixes, []

    def _run_fixes(self, issues: list[SonarIssue],
                   working_dir: str) -> list[FixResult]:
        return [self._generate_single_fix(i, working_dir) for i in issues]

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
                return _empty_fix(issue, source_context,
                                  "Empty response from agent")
            return FixResult(
                success=True, issue_key=issue.key,
                file_path=issue.file_path, original_code=source_context,
                fixed_code=raw, test_code="",
                explanation=f"Fix for {issue.rule}: {issue.message}",
            )
        except Exception as e:
            logger.error("Fix failed for %s: %s", issue.key, str(e))
            return _empty_fix(issue, source_context, str(e))

    # ── Scan Helpers ────────────────────────

    def _build_and_scan(self, project_dir: str, project_key: str,
                        project_name: str = None,
                        extra_args: list = None) -> bool:
        if not self._rebuild(project_dir):
            return False
        scan_ok = self._sonar.run_scanner(
            project_dir=project_dir, project_key=project_key,
            sonar_url=self._config.sonarqube.url,
            sonar_token=self._config.sonarqube.token,
            project_name=project_name, extra_args=extra_args,
        )
        if not scan_ok:
            logger.error("Scanner failed for %s", project_key)
            return False
        time.sleep(SCAN_SETTLE_SECONDS)
        return True

    def _rebuild(self, project_dir: str) -> bool:
        cmd = self._config.scanner.rebuild_command
        if not cmd:
            return True
        logger.info("Rebuilding project in %s", project_dir)
        result = subprocess.run(
            cmd, shell=True, cwd=project_dir,
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            logger.error("Rebuild failed: %s", result.stderr[-500:])
            return False
        return True

    # ── Delivery ────────────────────────────

    def _deliver_pr_comment(self, repo: str, pr_number: int,
                            issues, project_key: str, verified) -> None:
        comment = GitHubClient.format_issues_comment(
            issues=issues, project_key=project_key,
            sonar_url=self._config.sonarqube.url,
            fix_summary=_summarize_fixes(verified),
        )
        if self._config.pr_premerge.delivery == "comment" and repo:
            if self._github.comment_on_pr(repo, pr_number, comment):
                return
            logger.warning("PR comment failed — falling back to log")
        logger.info("PR comment (log delivery):\n%s", comment)

    def _create_nightly_fix_pr(self, project_dir: str, verified,
                               batch_cfg) -> str:
        if not batch_cfg.fix_pr_repo:
            logger.warning("create_fix_pr enabled but fix_pr.repo "
                           "not set — skipping PR creation")
            return ""
        branch = f"fix/sonarqube-nightly-{time.strftime('%Y%m%d-%H%M%S')}"
        title = (f"fix: resolve {len(verified)} SonarQube issue(s) "
                 f"[nightly batch]")
        if not self._github.push_fix_branch(project_dir, branch, title):
            return ""
        return self._github.create_fix_pr(
            repo=batch_cfg.fix_pr_repo, branch=branch,
            base=batch_cfg.fix_pr_base, title=title,
            body=_summarize_fixes(verified),
        )

    # ── Private Helpers ─────────────────────

    def _ephemeral_key(self, pr_number: int) -> str:
        return self._config.scanner.ephemeral_key_pattern.format(
            project=self._config.sonarqube.main_project_key,
            pr_number=pr_number,
        )

    def _disabled(self, mode: str) -> ModeResult:
        logger.warning("Mode %s is disabled in config", mode)
        return ModeResult(mode, self._config.sonarqube.main_project_key,
                          0, 0, 0, "DISABLED")

    @staticmethod
    def _build_result(mode, key, issues, fixes, verified, gate):
        return ModeResult(
            mode=mode, project_key=key,
            issues_found=len(issues), fixes_attempted=len(fixes),
            fixes_verified=len(verified), quality_gate=gate,
        )


def _limit(issues: list, max_issues: int) -> list:
    if max_issues and len(issues) > max_issues:
        logger.info("Limiting issues: %d -> %d", len(issues), max_issues)
        return issues[:max_issues]
    return issues


def _empty_fix(issue: SonarIssue, source: str, error: str) -> FixResult:
    return FixResult(
        success=False, issue_key=issue.key, file_path=issue.file_path,
        original_code=source, fixed_code="", test_code="",
        errors=[error],
    )


def _summarize_fixes(fixes: list[FixResult]) -> str:
    if not fixes:
        return "No automated fixes were generated."
    lines = [f"**{len(fixes)} fix(es)** verified by re-scan:\n"]
    for fix in fixes:
        lines.append(f"- `{fix.file_path}` — {fix.explanation}")
    return "\n".join(lines)
