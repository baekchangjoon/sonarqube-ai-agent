"""Token pricing for cost estimation of Bedrock Converse calls.

Claude Code CLI reports its own cost (total_cost_usd); this table is for
backends that only return token usage. Matched by substring against the
model ID, USD per 1M tokens (input, output). Unknown models return None
— report tokens only, never a guessed cost.
"""

PRICES_PER_MTOK = {
    "claude-opus-4": (5.00, 25.00),
    "claude-sonnet-4": (3.00, 15.00),
    "claude-haiku-4": (1.00, 5.00),
    "nova-2-lite": (0.30, 2.50),
    "nova-2-pro": (2.19, 17.50),
    "nova-pro": (0.80, 3.20),
    "nova-lite": (0.06, 0.24),
    "nova-micro": (0.035, 0.14),
}


def estimate_cost(model_id: str, input_tokens: int,
                  output_tokens: int):
    """Return estimated USD cost, or None if the model is unknown."""
    for key, (in_price, out_price) in PRICES_PER_MTOK.items():
        if key in model_id:
            return (input_tokens * in_price
                    + output_tokens * out_price) / 1_000_000
    return None
