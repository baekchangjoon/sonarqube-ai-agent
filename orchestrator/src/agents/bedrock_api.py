import json
import logging

from src.agents.base import LLMAgent

logger = logging.getLogger(__name__)


class BedrockAPIAgent(LLMAgent):
    """AWS Bedrock API fallback agent.

    Does NOT support MCP — the orchestrator must embed issue details
    directly into the prompt.
    """

    def __init__(self, model_id: str = "anthropic.claude-sonnet-4-20250514",
                 region: str = "us-east-1"):
        self._model_id = model_id
        self._region = region
        self._client = None

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
            response = self._invoke(prompt)
            return _extract_text(response)
        except Exception as e:
            logger.error("Bedrock API failed: %s", str(e))
            return ""

    def _invoke(self, prompt: str) -> dict:
        body = json.dumps({
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 4096,
            "anthropic_version": "bedrock-2023-05-31",
        })
        logger.info("Invoking Bedrock API (model=%s)", self._model_id)
        response = self._get_client().invoke_model(
            modelId=self._model_id, body=body,
        )
        return json.loads(response["body"].read())

    def supports_mcp(self) -> bool:
        return False

    def name(self) -> str:
        return f"Bedrock API ({self._model_id})"


def _extract_text(response_body: dict) -> str:
    blocks = response_body.get("content", [])
    return "".join(
        b.get("text", "") for b in blocks if b.get("type") == "text"
    )
