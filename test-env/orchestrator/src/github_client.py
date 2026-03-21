import logging
import subprocess
from dataclasses import dataclass

from src.sonarqube_client import SonarIssue

logger = logging.getLogger(__name__)

SEVERITY_EMOJI = {
    "BLOCKER": "[BLOCKER]",
    "CRITICAL": "[CRITICAL]",
    "MAJOR": "[MAJOR]",
    "MINOR": "[MINOR]",
    "INFO": "[INFO]",
}

TYPE_LABEL = {
    "BUG": "Bug",
    "VULNERABILITY": "Vulnerability",
    "CODE_SMELL": "Code Smell",
}


@dataclass
class PRComment:
    body: str
    repo: str
    pr_number: int


class GitHubClient:
    """Minimal GitHub client using the gh CLI.

    Uses `gh` instead of raw API to leverage existing git credentials.
    """

    @staticmethod
    def comment_on_pr(repo: str, pr_number: int,
                      body: str) -> bool:
        cmd = [
            "gh", "pr", "comment", str(pr_number),
            "--repo", repo, "--body", body,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error("gh pr comment failed: %s", result.stderr)
            return False
        logger.info("Commented on PR #%d in %s", pr_number, repo)
        return True

    @staticmethod
    def create_fix_pr(repo: str, branch: str, base: str,
                      title: str, body: str,
                      labels: list = None) -> str:
        cmd = [
            "gh", "pr", "create", "--repo", repo,
            "--head", branch, "--base", base,
            "--title", title, "--body", body,
        ]
        if labels:
            for label in labels:
                cmd.extend(["--label", label])

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error("gh pr create failed: %s", result.stderr)
            return ""
        pr_url = result.stdout.strip()
        logger.info("Created Fix PR: %s", pr_url)
        return pr_url

    @staticmethod
    def format_issues_comment(issues: list[SonarIssue],
                              project_key: str,
                              sonar_url: str,
                              fix_summary: str = "") -> str:
        header = _build_comment_header(len(issues))
        table_rows = _build_issue_rows(issues, sonar_url)
        footer = _build_comment_footer(
            issues, project_key, sonar_url, fix_summary
        )
        return "\n".join(header + table_rows + footer)


def _build_comment_header(issue_count: int) -> list[str]:
    return [
        "## SonarQube Analysis Report", "",
        f"**{issue_count} issue(s)** found.", "",
        "| Severity | Type | File | Line | Rule | Message |",
        "|----------|------|------|------|------|---------|",
    ]


def _build_issue_rows(issues: list[SonarIssue],
                      sonar_url: str) -> list[str]:
    rows = []
    for issue in issues[:30]:
        sev = SEVERITY_EMOJI.get(issue.severity, issue.severity)
        itype = TYPE_LABEL.get(issue.issue_type, issue.issue_type)
        rule_link = f"[{issue.rule}]({sonar_url}/coding_rules?rule_key={issue.rule})"
        msg = issue.message[:80]
        rows.append(
            f"| {sev} | {itype} | `{issue.file_path}` "
            f"| {issue.line} | {rule_link} | {msg} |"
        )
    if len(issues) > 30:
        rows.append(f"\n*... and {len(issues) - 30} more issues.*")
    return rows


def _build_comment_footer(issues: list[SonarIssue], project_key: str,
                          sonar_url: str, fix_summary: str) -> list[str]:
    lines = [
        "",
        f"[View in SonarQube]({sonar_url}/project/issues?id={project_key})",
    ]
    if fix_summary:
        lines.extend(["", "---", "", "### AI Fix Suggestions", "", fix_summary])
    return lines
