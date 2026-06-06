import logging
import subprocess

from src.agents.base import LLMAgent

logger = logging.getLogger(__name__)


class ClaudeCodeAgent(LLMAgent):
    """Anthropic Claude Code agent implementation.

    Requires: claude CLI >= 2.1.x with valid authentication.
    Flags: -p (print/headless), --permission-mode acceptEdits,
           stdin redirected from /dev/null to avoid 3s stdin wait.
    Reference: https://docs.anthropic.com/en/docs/claude-code
    """

    def __init__(self, allowed_tools: str = "Read,Write,Edit",
                 model: str = "sonnet"):
        self._allowed_tools = allowed_tools
        self._model = model

    def generate_fix(self, prompt: str,
                     working_dir: str) -> str:
        cmd = self._build_cmd(prompt)
        logger.info("Invoking Claude Code (model=%s)", self._model)
        return self._run(cmd, working_dir)

    def generate_triage(self, prompt: str,
                        working_dir: str) -> str:
        cmd = [
            "claude", "-p",
            "--allowedTools", "Read",  # judgment only — no edits
            "--model", self._model,
            prompt,
        ]
        logger.info("Invoking Claude Code triage (model=%s)", self._model)
        return self._run(cmd, working_dir)

    def _build_cmd(self, prompt: str) -> list[str]:
        return [
            "claude", "-p",
            "--permission-mode", "acceptEdits",
            "--allowedTools", self._allowed_tools,
            "--model", self._model,
            prompt,
        ]

    def _run(self, cmd: list[str], cwd: str) -> str:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            cwd=cwd, timeout=300, stdin=subprocess.DEVNULL,
        )
        if result.returncode != 0:
            logger.error("Claude Code failed: %s", result.stderr[-300:])
            return ""
        return result.stdout

    def supports_mcp(self) -> bool:
        return True

    def name(self) -> str:
        return f"Claude Code ({self._model})"
