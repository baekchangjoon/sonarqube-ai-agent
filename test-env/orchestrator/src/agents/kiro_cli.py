import logging
import subprocess

from src.agents.base import LLMAgent

logger = logging.getLogger(__name__)


class KiroCLIAgent(LLMAgent):
    """AWS Kiro CLI agent implementation.

    Invokes kiro-cli in --no-interactive mode with MCP server support.
    Reference: https://kiro.dev/docs/cli/reference/cli-commands
    """

    def __init__(self, agent_name: str = "sonarqube-fixer",
                 trust_all_tools: bool = True):
        self._agent_name = agent_name
        self._trust_all_tools = trust_all_tools

    def generate_fix(self, prompt: str,
                     working_dir: str) -> str:
        cmd = ["kiro-cli", "chat", "--no-interactive"]

        if self._trust_all_tools:
            cmd.append("--trust-all-tools")

        cmd.extend(["--agent", self._agent_name, prompt])

        logger.info("Invoking Kiro CLI (agent=%s)", self._agent_name)
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            cwd=working_dir, timeout=300,
        )

        if result.returncode != 0:
            logger.error("Kiro CLI failed: %s", result.stderr[-300:])
            return ""

        return result.stdout

    def supports_mcp(self) -> bool:
        return True

    def name(self) -> str:
        return f"Kiro CLI ({self._agent_name})"
