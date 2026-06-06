import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class AgentType(Enum):
    KIRO_CLI = "kiro-cli"
    CLAUDE_CODE = "claude-code"
    GEMINI_CLI = "gemini-cli"
    BEDROCK_API = "bedrock-api"


@dataclass
class FixResult:
    success: bool
    issue_key: str
    file_path: str
    original_code: str
    fixed_code: str
    test_code: str
    explanation: str = ""
    errors: list = field(default_factory=list)
    # LLM self-reported confidence (0.0-1.0) that the fix is correct;
    # None when the agent response did not include one
    fix_confidence: float = None


@dataclass
class TriageResult:
    """LLM judgment on whether a SonarQube issue is a real defect."""
    verdict: str       # "TRUE_POSITIVE" | "FALSE_POSITIVE"
    confidence: float  # 0.0-1.0, LLM self-reported (not calibrated)
    reason: str = ""


class LLMAgent(ABC):
    """Abstract interface for LLM-based code fixing agents.

    Every implementation must support:
    1. Generating fix code for a SonarQube issue
    2. Generating test code for the fix
    3. Reporting whether it supports MCP natively
    """

    @abstractmethod
    def generate_fix(self, prompt: str,
                     working_dir: str) -> str:
        """Send a prompt and return the raw LLM response."""

    def generate_triage(self, prompt: str,
                        working_dir: str) -> str:
        """Run a read-only judgment prompt.

        Defaults to generate_fix; implementations should override with
        a read-only tool configuration where possible."""
        return self.generate_fix(prompt, working_dir)

    @abstractmethod
    def supports_mcp(self) -> bool:
        """Whether this agent natively connects to MCP servers."""

    @abstractmethod
    def name(self) -> str:
        """Human-readable agent name for logging."""

    def get_usage(self) -> dict:
        """Cumulative token usage and cost for this agent instance.

        cost_usd is None when the backend cannot determine it."""
        return getattr(self, "usage", {
            "input_tokens": 0, "output_tokens": 0, "cost_usd": None,
        })

    def build_fix_prompt(self, issue_rule: str, issue_message: str,
                         file_path: str, line: int,
                         source_context: str) -> str:
        return (
            f"Fix the following SonarQube issue by editing the file "
            f"in place.\n\n"
            f"Rule: {issue_rule}\n"
            f"Message: {issue_message}\n"
            f"File: {file_path}\n"
            f"Line: {line}\n\n"
            f"Source context (around line {line}):\n"
            f"```java\n{source_context}\n```\n\n"
            f"Requirements:\n"
            f"1. Edit {file_path} in place to fix ONLY the reported "
            f"issue. Do not change unrelated code.\n"
            f"2. Keep the existing code style.\n"
            f"3. The code must still compile after the fix.\n"
            f"4. After fixing, print as the LAST line of your response "
            f"exactly one JSON object:\n"
            f'{{"fix_confidence": <0.0-1.0>, "reason": "<one short '
            f'sentence>"}}\n'
            f"where fix_confidence is your confidence that the fix "
            f"correctly resolves the issue without side effects.\n"
        )

    def build_fix_or_escape_prompt(self, issue_rule: str,
                                   issue_message: str, file_path: str,
                                   line: int,
                                   source_context: str) -> str:
        """Option D first call: fix the issue OR escape as false positive."""
        return (
            f"Fix the following SonarQube issue by editing the file in "
            f"place — UNLESS you judge the finding to be a false "
            f"positive.\n\n"
            f"Rule: {issue_rule}\n"
            f"Message: {issue_message}\n"
            f"File: {file_path}\n"
            f"Line: {line}\n\n"
            f"Source context (around line {line}):\n"
            f"```java\n{source_context}\n```\n\n"
            f"First judge whether this finding is a FALSE positive (the "
            f"analyzer is wrong, or the finding does not apply in this "
            f"context). You may read files for more context.\n\n"
            f"If FALSE positive: do NOT modify any file, and respond "
            f"with only:\n"
            f'{{"verdict": "FALSE_POSITIVE", "reason": "<one short '
            f'sentence>"}}\n\n'
            f"If TRUE positive:\n"
            f"1. Edit {file_path} in place to fix ONLY the reported "
            f"issue. Do not change unrelated code.\n"
            f"2. Keep the existing code style.\n"
            f"3. The code must still compile after the fix.\n"
            f"4. Print as the LAST line of your response exactly one "
            f"JSON object:\n"
            f'{{"verdict": "FIXED", "reason": "<one short sentence>"}}\n'
        )

    def build_fix_review_prompt(self, issue_rule: str, issue_message: str,
                                file_path: str, line: int,
                                diff: str) -> str:
        """Option D second call: independent review of an applied fix."""
        return (
            f"You are an independent reviewer. Another AI agent modified "
            f"code to fix a SonarQube issue. Assess whether the change "
            f"correctly resolves the issue without side effects or "
            f"unrelated changes.\n\n"
            f"Rule: {issue_rule}\n"
            f"Message: {issue_message}\n"
            f"File: {file_path}\n"
            f"Line: {line}\n\n"
            f"Applied change (unified diff):\n"
            f"```diff\n{diff}\n```\n\n"
            f"You may read files for more context, but DO NOT modify "
            f"any file.\n"
            f"Respond with ONLY one JSON object as the last line:\n"
            f'{{"assessment": "APPROPRIATE" or "INAPPROPRIATE", '
            f'"confidence": <0.0-1.0>, "reason": "<one short sentence>"}}\n'
        )

    def build_fp_review_prompt(self, issue_rule: str, issue_message: str,
                               file_path: str, line: int,
                               source_context: str,
                               claim_reason: str) -> str:
        """Option D second call: independent review of an FP claim."""
        return (
            f"You are an independent reviewer. Another AI agent judged "
            f"the following SonarQube finding to be a FALSE positive and "
            f"skipped fixing it.\n"
            f"Claimed reason: {claim_reason}\n\n"
            f"Rule: {issue_rule}\n"
            f"Message: {issue_message}\n"
            f"File: {file_path}\n"
            f"Line: {line}\n\n"
            f"Source context (around line {line}):\n"
            f"```java\n{source_context}\n```\n\n"
            f"Assess whether the false-positive judgment is correct. "
            f"You may read files for more context, but DO NOT modify "
            f"any file.\n"
            f"Respond with ONLY one JSON object as the last line:\n"
            f'{{"assessment": "AGREE_FALSE_POSITIVE" or "DISAGREE", '
            f'"confidence": <0.0-1.0>, "reason": "<one short sentence>"}}\n'
        )

    def build_triage_prompt(self, issue_rule: str, issue_message: str,
                            file_path: str, line: int,
                            source_context: str) -> str:
        return (
            f"You are reviewing a static analysis finding. Judge whether "
            f"it is a TRUE positive (a real issue worth fixing) or a "
            f"FALSE positive (the analyzer is wrong, or the finding does "
            f"not apply in this context).\n\n"
            f"Rule: {issue_rule}\n"
            f"Message: {issue_message}\n"
            f"File: {file_path}\n"
            f"Line: {line}\n\n"
            f"Source context (around line {line}):\n"
            f"```java\n{source_context}\n```\n\n"
            f"You may read files for more context, but DO NOT modify "
            f"any file.\n"
            f"Respond with ONLY one JSON object as the last line:\n"
            f'{{"verdict": "TRUE_POSITIVE" or "FALSE_POSITIVE", '
            f'"confidence": <0.0-1.0>, "reason": "<one short sentence>"}}\n'
        )
