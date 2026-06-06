import difflib
import json
import logging
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from src.agents.base import FixResult, LLMAgent, TriageResult
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
    issues_skipped_as_fp: int = 0


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
        # Judge role (FP triage, fix review): harness-free judgment
        # calls, routable to a different backend/model than the fixer.
        if config.agent.judge_type or config.agent.judge_model:
            self._judge: LLMAgent = AgentFactory.create(
                config.agent,
                agent_type=config.agent.judge_type or None,
                model=config.agent.judge_model or None,
            )
        else:
            self._judge = self._agent
        self._github = GitHubClient()

        logger.info(
            "Orchestrator initialized (fixer=%s, judge=%s, sonar=%s, "
            "pr_mode=%s)",
            self._agent.name(), self._judge.name(),
            config.sonarqube.url, config.scanner.pr_mode,
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

        fixes, verified, skipped = self._fix_and_verify(
            issues, project_dir, ephemeral_key, scan_project_name=pr_name,
        )
        self._push_pr_fix_commit(project_dir, pr_number, verified)
        self._deliver_pr_comment(repo, pr_number, issues,
                                 ephemeral_key, verified, skipped)
        return self._build_result("pr_premerge", ephemeral_key,
                                  issues, fixes, verified, gate, skipped)

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

        fixes, verified, skipped = self._fix_and_verify(
            issues, project_dir, main_key,
            pull_request=pr_key, scan_extra_args=extra_args,
        )
        self._push_pr_fix_commit(project_dir, pr_number, verified)
        self._deliver_pr_comment(repo, pr_number, issues, main_key,
                                 verified, skipped)
        return self._build_result("pr_premerge", main_key,
                                  issues, fixes, verified, gate, skipped)

    def cleanup_pr_project(self, pr_number: int) -> bool:
        if self._config.scanner.pr_mode == "native":
            return True  # no ephemeral project to delete
        return self._sonar.delete_project(self._ephemeral_key(pr_number))

    # ── Mode 2: Post-merge ──────────────────

    def handle_post_merge(self,
                          project_dir: str = None) -> ModeResult:
        if not self._config.post_merge.enabled:
            return self._disabled("post_merge")

        pm_cfg = self._config.post_merge
        main_key = self._config.sonarqube.main_project_key
        logger.info("Mode 2: Post-merge analysis (%s)", main_key)

        if project_dir:
            self._build_and_scan(project_dir, main_key)
        issues = self._sonar.get_new_issues(main_key)
        gate = self._sonar.get_quality_gate_status(main_key)
        logger.info("Post-merge: %d new issues, gate=%s", len(issues), gate)

        if not issues:
            return ModeResult("post_merge", main_key, 0, 0, 0, gate)
        issues = _limit(issues, pm_cfg.max_issues_per_run)

        fixes, verified, skipped = self._fix_with_optional_verify(
            issues, project_dir, main_key,
        )
        if pm_cfg.create_fix_pr and verified:
            self._create_fix_pr_from_fixes(
                project_dir, verified, skipped, pm_cfg.fix_pr_repo,
                pm_cfg.fix_pr_base, "post-merge",
            )
        return self._build_result("post_merge", main_key,
                                  issues, fixes, verified, gate, skipped)

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

        fixes, verified, skipped = self._fix_with_optional_verify(
            issues, project_dir, main_key,
        )
        if batch_cfg.create_fix_pr and verified:
            self._create_fix_pr_from_fixes(
                project_dir, verified, skipped, batch_cfg.fix_pr_repo,
                batch_cfg.fix_pr_base, "nightly",
            )
        return self._build_result("nightly_batch", main_key,
                                  issues, fixes, verified, gate, skipped)

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
        """Triage, run fixes, then re-scan and count an issue as
        verified only if it is no longer open."""
        fixes, skipped = self._triage_and_fix(issues, project_dir)
        if not any(f.success for f in fixes):
            return fixes, [], skipped

        if not self._build_and_scan(project_dir, project_key,
                                    project_name=scan_project_name,
                                    extra_args=scan_extra_args):
            logger.warning("Verification re-scan failed — fixes unverified")
            return fixes, [], skipped

        still_open = {
            i.key for i in self._sonar.get_open_issues(
                project_key, max_results=500, pull_request=pull_request,
            )
        }
        verified = [f for f in fixes
                    if f.success and f.issue_key not in still_open]
        logger.info("Verification: %d/%d fixes confirmed by re-scan",
                    len(verified), len(fixes))
        return fixes, verified, skipped

    def _fix_with_optional_verify(self, issues, project_dir, project_key):
        if project_dir:
            return self._fix_and_verify(issues, project_dir, project_key)
        logger.warning("No --project-dir given — fixes cannot be "
                       "applied locally or verified")
        fixes, skipped = self._triage_and_fix(issues, ".")
        return fixes, [], skipped

    # ── False Positive / Fix-quality Assessment ──

    def _triage_and_fix(self, issues: list[SonarIssue],
                        working_dir: str):
        """Dispatch on the configured assessment strategy.

        "triage" (C): read-only pre-fix judgment, FP → skip + report.
        "review" (D): fix-with-FP-escape, then an independent LLM call
                      assesses the applied fix or the FP claim.
        "none":       fix everything.
        """
        strategy = self._config.assessment.strategy
        if strategy == "review":
            return self._fix_with_post_review(issues, working_dir)

        fixes, skipped = [], []
        for issue in issues:
            if strategy == "triage":
                triage = self._triage_issue(issue, working_dir)
                if triage.verdict == "FALSE_POSITIVE":
                    logger.info(
                        "FP triage skip: %s %s (confidence=%.2f) — %s",
                        issue.rule, issue.key, triage.confidence,
                        triage.reason,
                    )
                    skipped.append((issue, triage))
                    continue
            fixes.append(self._generate_single_fix(issue, working_dir))
        return fixes, skipped

    def _triage_issue(self, issue: SonarIssue,
                      working_dir: str) -> TriageResult:
        prompt = self._judge.build_triage_prompt(
            issue_rule=issue.rule, issue_message=issue.message,
            file_path=issue.file_path, line=issue.line,
            source_context=self._get_source_context(issue),
        )
        try:
            raw = self._judge.generate_triage(prompt, working_dir)
        except Exception as e:
            logger.warning("Triage failed for %s: %s — treating as "
                           "true positive", issue.key, e)
            return TriageResult("TRUE_POSITIVE", 0.0, f"triage error: {e}")

        data = _extract_json(raw)
        if (not data
                or data.get("verdict") not in ("TRUE_POSITIVE",
                                               "FALSE_POSITIVE")):
            logger.warning("Unparseable triage for %s — treating as "
                           "true positive", issue.key)
            return TriageResult("TRUE_POSITIVE", 0.0,
                                "unparseable triage response")
        return TriageResult(
            verdict=data["verdict"],
            confidence=_safe_float(data.get("confidence"), 0.0),
            reason=str(data.get("reason", "")),
        )

    # ── Option D: fix-with-escape + independent review ──

    def _fix_with_post_review(self, issues: list[SonarIssue],
                              working_dir: str):
        fixes, skipped = [], []
        for issue in issues:
            kind, result = self._fix_or_escape(issue, working_dir)
            if kind == "skip":
                skipped.append(result)
            else:
                fixes.append(result)
        return fixes, skipped

    def _fix_or_escape(self, issue: SonarIssue, working_dir: str):
        source_context = self._get_source_context(issue)
        prompt = self._agent.build_fix_or_escape_prompt(
            issue_rule=issue.rule, issue_message=issue.message,
            file_path=issue.file_path, line=issue.line,
            source_context=source_context,
        )
        target = Path(working_dir) / issue.file_path
        before = target.read_text() if target.exists() else ""

        try:
            raw = self._agent.generate_fix(prompt, working_dir)
        except Exception as e:
            logger.error("Fix failed for %s: %s", issue.key, str(e))
            return "fix", _empty_fix(issue, source_context, str(e))

        after = target.read_text() if target.exists() else ""
        data = _extract_json(raw) or {}

        if before != after:  # a fix was applied — review the diff
            return "fix", self._build_reviewed_fix(
                issue, source_context, raw, before, after, working_dir,
            )
        if data.get("verdict") == "FALSE_POSITIVE":
            return "skip", self._build_reviewed_fp_skip(
                issue, source_context, str(data.get("reason", "")),
                working_dir,
            )
        return "fix", _empty_fix(
            issue, source_context,
            "No change applied and no false-positive verdict",
        )

    def _build_reviewed_fix(self, issue, source_context, raw,
                            before, after, working_dir) -> FixResult:
        diff = _unified_diff(before, after, issue.file_path)
        review = self._review_outcome(
            self._judge.build_fix_review_prompt(
                issue_rule=issue.rule, issue_message=issue.message,
                file_path=issue.file_path, line=issue.line, diff=diff,
            ),
            issue, working_dir, ("APPROPRIATE", "INAPPROPRIATE"),
        )
        explanation = f"Fix for {issue.rule}: {issue.message}"
        if review.verdict != "APPROPRIATE":
            explanation += f" [review: {review.verdict} — {review.reason}]"
        logger.info("Fix review: %s %s (confidence=%s)",
                    issue.key, review.verdict,
                    _fmt_confidence(review.confidence))
        return FixResult(
            success=True, issue_key=issue.key,
            file_path=issue.file_path, original_code=source_context,
            fixed_code=raw, test_code="", explanation=explanation,
            fix_confidence=review.confidence,
        )

    def _build_reviewed_fp_skip(self, issue, source_context,
                                claim_reason, working_dir):
        review = self._review_outcome(
            self._judge.build_fp_review_prompt(
                issue_rule=issue.rule, issue_message=issue.message,
                file_path=issue.file_path, line=issue.line,
                source_context=source_context, claim_reason=claim_reason,
            ),
            issue, working_dir, ("AGREE_FALSE_POSITIVE", "DISAGREE"),
        )
        if review.verdict == "DISAGREE":
            reason = (f"claim: {claim_reason}; reviewer DISAGREES — "
                      f"human review required ({review.reason})")
        else:
            reason = f"claim: {claim_reason}; review: {review.reason}"
        logger.info("FP claim review: %s %s (confidence=%s)",
                    issue.key, review.verdict,
                    _fmt_confidence(review.confidence))
        return issue, TriageResult("FALSE_POSITIVE",
                                   review.confidence, reason)

    def _review_outcome(self, prompt, issue, working_dir,
                        valid_assessments) -> TriageResult:
        """Independent read-only LLM assessment of a fix or FP claim."""
        try:
            raw = self._judge.generate_triage(prompt, working_dir)
        except Exception as e:
            logger.warning("Review failed for %s: %s", issue.key, e)
            return TriageResult("UNKNOWN", None, f"review error: {e}")
        data = _extract_json(raw)
        if not data or data.get("assessment") not in valid_assessments:
            logger.warning("Unparseable review for %s", issue.key)
            return TriageResult("UNKNOWN", None,
                                "unparseable review response")
        return TriageResult(
            verdict=data["assessment"],
            confidence=_safe_float(data.get("confidence"), None),
            reason=str(data.get("reason", "")),
        )

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
                fix_confidence=_extract_fix_confidence(raw),
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
                            issues, project_key: str, verified,
                            skipped=None) -> None:
        comment = GitHubClient.format_issues_comment(
            issues=issues, project_key=project_key,
            sonar_url=self._config.sonarqube.url,
            fix_summary=_summarize_fixes(verified),
            fp_summary=_summarize_fp_skips(skipped),
        )
        if self._config.pr_premerge.delivery == "comment" and repo:
            if self._github.comment_on_pr(repo, pr_number, comment):
                return
            logger.warning("PR comment failed — falling back to log")
        logger.info("PR comment (log delivery):\n%s", comment)

    def _push_pr_fix_commit(self, project_dir: str, pr_number: int,
                            verified) -> None:
        """Mode 1: push verified fixes as a new commit to the PR branch."""
        if not verified or not self._config.pr_premerge.push_fix_commit:
            return
        message = (f"fix: resolve {len(verified)} SonarQube issue(s) "
                   f"via AI agent (PR #{pr_number})"
                   f"{_confidence_note(verified)}")
        if not self._github.commit_and_push(project_dir, message):
            logger.warning("Failed to push fix commit to PR branch")

    def _create_fix_pr_from_fixes(self, project_dir: str, verified,
                                  skipped, repo: str, base: str,
                                  label: str) -> str:
        """Mode 2/3: push verified fixes to a new branch and open a PR."""
        if not repo:
            logger.warning("create_fix_pr enabled but fix_pr.repo "
                           "not set — skipping PR creation")
            return ""
        branch = (f"fix/sonarqube-{label}-"
                  f"{time.strftime('%Y%m%d-%H%M%S')}")
        title = (f"fix: resolve {len(verified)} SonarQube issue(s) "
                 f"[{label}]")
        if not self._github.push_fix_branch(
                project_dir, branch, title + _confidence_note(verified)):
            return ""
        body = _summarize_fixes(verified)
        fp_summary = _summarize_fp_skips(skipped)
        if fp_summary:
            body += f"\n\n### False Positive Screening\n\n{fp_summary}"
        return self._github.create_fix_pr(
            repo=repo, branch=branch, base=base, title=title, body=body,
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
    def _build_result(mode, key, issues, fixes, verified, gate,
                      skipped=None):
        return ModeResult(
            mode=mode, project_key=key,
            issues_found=len(issues), fixes_attempted=len(fixes),
            fixes_verified=len(verified), quality_gate=gate,
            issues_skipped_as_fp=len(skipped or []),
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
    lines = [f"**{len(fixes)} fix(es)** verified by re-scan "
             f"(confidence = LLM-assessed):\n"]
    for fix in fixes:
        lines.append(f"- `{fix.file_path}` — {fix.explanation} "
                     f"[fix confidence: {_fmt_confidence(fix.fix_confidence)}]")
    return "\n".join(lines)


def _summarize_fp_skips(skipped) -> str:
    """Report issues the LLM triage judged as false positives."""
    if not skipped:
        return ""
    lines = [f"**{len(skipped)} issue(s)** judged as false positive "
             f"and skipped (confidence = LLM-assessed, please review):\n"]
    for issue, triage in skipped:
        lines.append(
            f"- `{issue.file_path}:{issue.line}` {issue.rule} — "
            f"{triage.reason} [confidence: "
            f"{_fmt_confidence(triage.confidence)}]"
        )
    return "\n".join(lines)


def _confidence_note(verified) -> str:
    """Aggregate fix-confidence line for commit messages / PR titles."""
    confs = [f.fix_confidence for f in verified
             if f.fix_confidence is not None]
    if not confs:
        return ""
    return (f"\n\nFix confidence (LLM-assessed): "
            f"avg {sum(confs) / len(confs):.2f}, min {min(confs):.2f}")


def _fmt_confidence(value) -> str:
    return f"{value:.2f}" if value is not None else "n/a"


def _extract_fix_confidence(raw: str):
    data = _extract_json(raw)
    if data and "fix_confidence" in data:
        return _safe_float(data["fix_confidence"], None)
    return None


def _extract_json(text) -> dict:
    """Extract the last parseable JSON object from an LLM response."""
    if not isinstance(text, str):
        return None
    for match in reversed(re.findall(r"\{[^{}]*\}", text)):
        try:
            return json.loads(match)
        except ValueError:
            continue
    return None


def _safe_float(value, default):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _unified_diff(before: str, after: str, file_path: str,
                  max_chars: int = 6000) -> str:
    diff = "".join(difflib.unified_diff(
        before.splitlines(keepends=True), after.splitlines(keepends=True),
        fromfile=f"a/{file_path}", tofile=f"b/{file_path}",
    ))
    if len(diff) > max_chars:
        diff = diff[:max_chars] + "\n... (diff truncated)"
    return diff
