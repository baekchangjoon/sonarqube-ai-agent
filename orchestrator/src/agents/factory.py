import logging

from src.agents.base import AgentType, LLMAgent
from src.agents.bedrock_api import BedrockAPIAgent
from src.agents.claude_code import ClaudeCodeAgent
from src.agents.gemini_cli import GeminiCLIAgent
from src.agents.kiro_cli import KiroCLIAgent
from src.config import AgentConfig

logger = logging.getLogger(__name__)


def _build_kiro(cfg: AgentConfig, model: str) -> LLMAgent:
    return KiroCLIAgent(
        agent_name=cfg.kiro.get("agent_name", "sonarqube-fixer"),
        trust_all_tools=cfg.kiro.get("trust_all_tools", True),
    )


def _build_claude(cfg: AgentConfig, model: str) -> LLMAgent:
    return ClaudeCodeAgent(
        allowed_tools=cfg.claude.get("allowed_tools", "Read,Write,Edit"),
        model=model or cfg.claude.get("model", "sonnet"),
    )


def _build_gemini(cfg: AgentConfig, model: str) -> LLMAgent:
    return GeminiCLIAgent()


def _build_bedrock(cfg: AgentConfig, model: str) -> LLMAgent:
    return BedrockAPIAgent(
        model_id=model or cfg.bedrock.get(
            "model_id", "anthropic.claude-sonnet-4-20250514"
        ),
        region=cfg.bedrock.get("region", "us-east-1"),
    )


_AGENT_BUILDERS = {
    AgentType.KIRO_CLI: _build_kiro,
    AgentType.CLAUDE_CODE: _build_claude,
    AgentType.GEMINI_CLI: _build_gemini,
    AgentType.BEDROCK_API: _build_bedrock,
}


class AgentFactory:
    """Creates LLM agent instances from configuration.

    Supports runtime switching via config.yml agent.type, and per-role
    overrides (e.g. a judge agent with a different backend/model).
    """

    @staticmethod
    def create(config: AgentConfig, agent_type: str = None,
               model: str = None) -> LLMAgent:
        resolved = AgentType(agent_type or config.type)
        logger.info("Creating agent: %s%s", resolved.value,
                    f" (model={model})" if model else "")

        builder = _AGENT_BUILDERS.get(resolved)
        if builder is None:
            raise ValueError(f"Unsupported agent type: {resolved.value}")
        return builder(config, model)
