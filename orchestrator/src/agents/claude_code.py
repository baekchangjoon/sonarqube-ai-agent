import json
import logging
import subprocess

from src.agents.base import LLMAgent

logger = logging.getLogger(__name__)


class ClaudeCodeAgent(LLMAgent):
    """Anthropic Claude Code agent implementation.

    Requires: claude CLI >= 2.1.x with valid authentication.
    Flags: -p (print/headless), --permission-mode acceptEdits,
           --output-format json (for usage/cost reporting),
           stdin redirected from /dev/null to avoid 3s stdin wait.
    Works against the Anthropic API or AWS Bedrock
    (CLAUDE_CODE_USE_BEDROCK=1).
    Reference: https://docs.anthropic.com/en/docs/claude-code
    """

    def __init__(self, allowed_tools: str = "Read,Write,Edit",
                 model: str = "sonnet"):
        self._allowed_tools = allowed_tools
        self._model = model
        self.usage = {"input_tokens": 0, "output_tokens": 0,
                      "cost_usd": 0.0}

    def generate_fix(self, prompt: str,
                     working_dir: str) -> str:
        cmd = self._build_cmd(prompt)
        logger.info("Invoking Claude Code (model=%s)", self._model)
        return self._run(cmd, working_dir)

    def generate_triage(self, prompt: str,
                        working_dir: str) -> str:
        cmd = [
            "claude", "-p",
            "--output-format", "json",
            "--allowedTools", "Read",  # judgment only — no edits
            "--model", self._model,
            prompt,
        ]
        logger.info("Invoking Claude Code triage (model=%s)", self._model)
        return self._run(cmd, working_dir)

    def supports_readonly_triage(self) -> bool:
        # generate_triage restricts tools to Read — no file edits.
        return True

    def _build_cmd(self, prompt: str) -> list[str]:
        return [
            "claude", "-p",
            "--output-format", "json",
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
            # usage-limit / API errors land on stdout as JSON, not stderr
            logger.error("Claude Code failed (rc=%d): stderr=%s stdout=%s",
                         result.returncode, result.stderr[-300:],
                         result.stdout[-300:])
            return ""
        return self._parse_cli_json(result.stdout)

    def _parse_cli_json(self, stdout: str) -> str:
        """Extract the response text and record usage from the CLI's
        JSON envelope; fall back to raw stdout if it isn't JSON."""
        try:
            data = json.loads(stdout)
        except ValueError:
            return stdout
        usage = data.get("usage", {})
        self.usage["input_tokens"] += (
            usage.get("input_tokens", 0)
            + usage.get("cache_creation_input_tokens", 0)
            + usage.get("cache_read_input_tokens", 0)
        )
        self.usage["output_tokens"] += usage.get("output_tokens", 0)
        self.usage["cost_usd"] += data.get("total_cost_usd", 0.0) or 0.0
        return data.get("result", "") or ""

    def supports_mcp(self) -> bool:
        return True

    def name(self) -> str:
        return f"Claude Code ({self._model})"
