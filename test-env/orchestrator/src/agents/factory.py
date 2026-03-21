import logging

from src.agents.base import AgentType, LLMAgent
from src.agents.bedrock_api import BedrockAPIAgent
from src.agents.claude_code import ClaudeCodeAgent
from src.agents.gemini_cli import GeminiCLIAgent
from src.agents.kiro_cli import KiroCLIAgent
from src.config import AgentConfig

logger = logging.getLogger(__name__)

_AGENT_BUILDERS = {
    AgentType.KIRO_CLI: lambda cfg: KiroCLIAgent(
        agent_name=cfg.kiro.get("agent_name", "sonarqube-fixer"),
        trust_all_tools=cfg.kiro.get("trust_all_tools", True),
    ),
    AgentType.CLAUDE_CODE: lambda cfg: ClaudeCodeAgent(
        allowed_tools=cfg.claude.get("allowed_tools", "Read,Write,Edit"),
        model=cfg.claude.get("model", "sonnet"),
    ),
    AgentType.GEMINI_CLI: lambda cfg: GeminiCLIAgent(),
    AgentType.BEDROCK_API: lambda cfg: BedrockAPIAgent(
        model_id=cfg.bedrock.get("model_id", "anthropic.claude-sonnet-4-20250514"),
        region=cfg.bedrock.get("region", "us-east-1"),
    ),
}


class AgentFactory:
    """Creates LLM agent instances from configuration.

    Supports runtime switching via config.yml agent.type field.
    """

    @staticmethod
    def create(config: AgentConfig) -> LLMAgent:
        agent_type = AgentType(config.type)
        logger.info("Creating agent: %s", agent_type.value)

        builder = _AGENT_BUILDERS.get(agent_type)
        if builder is None:
            raise ValueError(f"Unsupported agent type: {config.type}")
        return builder(config)
