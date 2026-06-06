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
