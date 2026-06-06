import pytest

from src.agents.base import AgentType, LLMAgent, FixResult
from src.agents.factory import AgentFactory
from src.agents.kiro_cli import KiroCLIAgent
from src.agents.claude_code import ClaudeCodeAgent
from src.agents.gemini_cli import GeminiCLIAgent
from src.agents.bedrock_api import BedrockAPIAgent
from src.config import AgentConfig


class TestAgentFactory:

    def test_create_kiro_cli(self):
        config = AgentConfig(
            type="kiro-cli",
            kiro={"agent_name": "test-agent", "trust_all_tools": False},
        )
        agent = AgentFactory.create(config)
        assert isinstance(agent, KiroCLIAgent)
        assert agent.supports_mcp() is True
        assert "Kiro" in agent.name()

    def test_create_claude_code(self):
        config = AgentConfig(
            type="claude-code",
            claude={"model": "opus"},
        )
        agent = AgentFactory.create(config)
        assert isinstance(agent, ClaudeCodeAgent)
        assert agent.supports_mcp() is True
        assert "opus" in agent.name()

    def test_create_gemini_cli(self):
        config = AgentConfig(type="gemini-cli")
        agent = AgentFactory.create(config)
        assert isinstance(agent, GeminiCLIAgent)
        assert agent.supports_mcp() is True

    def test_create_bedrock_api(self):
        config = AgentConfig(
            type="bedrock-api",
            bedrock={"model_id": "test-model", "region": "eu-west-1"},
        )
        agent = AgentFactory.create(config)
        assert isinstance(agent, BedrockAPIAgent)
        assert agent.supports_mcp() is False
        assert "test-model" in agent.name()

    def test_create_invalid_type_raises(self):
        config = AgentConfig(type="nonexistent-agent")
        with pytest.raises(ValueError):
            AgentFactory.create(config)


class TestLLMAgentInterface:

    def test_build_fix_prompt_contains_required_fields(self):
        config = AgentConfig(type="kiro-cli")
        agent = AgentFactory.create(config)

        prompt = agent.build_fix_prompt(
            issue_rule="java:S2259",
            issue_message="NullPointerException may be thrown",
            file_path="src/main/java/Foo.java",
            line=42,
            source_context="String x = null;\nx.length();",
        )

        assert "java:S2259" in prompt
        assert "NullPointerException" in prompt
        assert "Foo.java" in prompt
        assert "42" in prompt
        assert "in place" in prompt


class TestFixResult:

    def test_success_result(self):
        result = FixResult(
            success=True,
            issue_key="AX123",
            file_path="Foo.java",
            original_code="bad code",
            fixed_code="good code",
            test_code="test code",
        )
        assert result.success is True
        assert result.errors == []

    def test_failure_result(self):
        result = FixResult(
            success=False,
            issue_key="AX456",
            file_path="Bar.java",
            original_code="",
            fixed_code="",
            test_code="",
            errors=["timeout"],
        )
        assert result.success is False
        assert "timeout" in result.errors
