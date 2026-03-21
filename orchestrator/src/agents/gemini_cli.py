import logging
import subprocess

from src.agents.base import LLMAgent

logger = logging.getLogger(__name__)


class GeminiCLIAgent(LLMAgent):
    """Google Gemini CLI agent implementation.

    Requires: gemini CLI >= 0.30.x with cached credentials.
    Flags: --yolo (auto-approve all tool calls), -p (headless prompt).
    Reference: https://github.com/google-gemini/gemini-cli
    """

    def generate_fix(self, prompt: str,
                     working_dir: str) -> str:
        cmd = ["gemini", "--yolo", "-p", prompt]

        logger.info("Invoking Gemini CLI")
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            cwd=working_dir, timeout=300,
        )

        if result.returncode != 0:
            logger.error("Gemini CLI failed: %s", result.stderr[-300:])
            return ""

        return result.stdout

    def supports_mcp(self) -> bool:
        return True

    def name(self) -> str:
        return "Gemini CLI"
