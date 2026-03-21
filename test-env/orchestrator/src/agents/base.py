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
            f"Fix the following SonarQube issue.\n\n"
            f"Rule: {issue_rule}\n"
            f"Message: {issue_message}\n"
            f"File: {file_path}\n"
            f"Line: {line}\n\n"
            f"Source context:\n```java\n{source_context}\n```\n\n"
            f"Requirements:\n"
            f"1. Fix ONLY the reported issue. Do not change unrelated code.\n"
            f"2. Generate a JUnit 5 test that verifies the fix.\n"
            f"3. Follow Google Java Style Guide.\n"
            f"4. Return the fix as a unified diff and the test as a "
            f"complete Java file.\n"
        )
