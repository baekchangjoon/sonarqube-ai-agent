import logging

from src.agents.base import LLMAgent

logger = logging.getLogger(__name__)


class BedrockAPIAgent(LLMAgent):
    """AWS Bedrock agent using the Converse API.

    Model-agnostic (Claude, Nova, ...) single-shot calls — suitable for
    judgment roles (triage, review). Does NOT support file editing or
    MCP: there is no tool-execution harness, so fixes are suggestion-only.

    Accumulates token usage from Converse responses (for cost reporting).
    """

    def __init__(self, model_id: str = "anthropic.claude-sonnet-4-20250514",
                 region: str = "us-east-1"):
        self._model_id = model_id
        self._region = region
        self._client = None
        self.usage = {"input_tokens": 0, "output_tokens": 0}

    def _get_client(self):
        if self._client is None:
            import boto3
            self._client = boto3.client(
                "bedrock-runtime", region_name=self._region
            )
        return self._client

    def generate_fix(self, prompt: str,
                     working_dir: str) -> str:
        try:
            response = self._get_client().converse(
                modelId=self._model_id,
                messages=[{"role": "user", "content": [{"text": prompt}]}],
                inferenceConfig={"maxTokens": 4096},
            )
            self._record_usage(response.get("usage", {}))
            return _extract_text(response)
        except Exception as e:
            logger.error("Bedrock Converse failed: %s", str(e))
            return ""

    def _record_usage(self, usage: dict) -> None:
        self.usage["input_tokens"] += usage.get("inputTokens", 0)
        self.usage["output_tokens"] += usage.get("outputTokens", 0)

    def supports_mcp(self) -> bool:
        return False

    def name(self) -> str:
        return f"Bedrock Converse ({self._model_id})"


def _extract_text(response: dict) -> str:
    content = (response.get("output", {})
               .get("message", {})
               .get("content", []))
    return "".join(block.get("text", "") for block in content)
