"""
Token cost estimation for LLM API calls.

Pricing is approximate and should be updated when provider pricing changes.
"""

# Per-million-token pricing (USD) by provider + model pattern
# Sources: provider pricing pages as of 2026-04
PRICING = {
    # OpenAI-compatible (DeepSeek, Tongyi, SiliconFlow, etc.)
    "deepseek": {"input": 0.27, "output": 1.10},
    "qwen": {"input": 0.50, "output": 2.00},
    "tongyi": {"input": 0.50, "output": 2.00},
    "siliconflow": {"input": 0.14, "output": 0.28},
    # Zhipu GLM
    "glm": {"input": 0.50, "output": 2.00},
    "zhipu": {"input": 0.50, "output": 2.00},
    # Default fallback
    "default": {"input": 0.50, "output": 2.00},
}


def estimate_cost(tokens_in: int, tokens_out: int, model: str = "") -> float:
    """Estimate USD cost for a single LLM call."""
    key = "default"
    model_lower = model.lower()
    for provider in PRICING:
        if provider in model_lower:
            key = provider
            break
    pricing = PRICING[key]
    return (tokens_in * pricing["input"] + tokens_out * pricing["output"]) / 1_000_000


def aggregate_task_cost(stages: list) -> dict:
    """Aggregate token usage and cost across pipeline stages.

    Args:
        stages: list of stage dicts from pipeline_stages table,
                each with 'stage' and 'result' keys.

    Returns:
        {total_tokens_in, total_tokens_out, total_tokens,
         estimated_cost_usd, by_stage: {stage: {tokens, cost}}}
    """
    total_in = 0
    total_out = 0
    by_stage = {}

    for s in stages:
        result = s.get("result")
        if not result:
            continue
        if isinstance(result, str):
            try:
                import json
                result = json.loads(result)
            except (json.JSONDecodeError, TypeError):
                continue

        # Extract token usage from various result formats
        # Priority: _token_usage (injected by orchestrator) > usage > token_usage
        usage = result.get("_token_usage") or result.get("usage") or result.get("token_usage") or {}
        tokens_in = usage.get("prompt_tokens", 0)
        tokens_out = usage.get("completion_tokens", 0)
        model = result.get("model", "")

        # Some agents store per-page usage
        if not tokens_in and not tokens_out:
            pages = result.get("pages") or result.get("slides") or []
            for p in pages:
                p_usage = p.get("usage") or p.get("token_usage") or {}
                tokens_in += p_usage.get("prompt_tokens", 0)
                tokens_out += p_usage.get("completion_tokens", 0)
                model = model or p.get("model", "")

        if tokens_in or tokens_out:
            cost = estimate_cost(tokens_in, tokens_out, model)
            by_stage[s["stage"]] = {
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "tokens_total": tokens_in + tokens_out,
                "cost_usd": round(cost, 6),
            }
            total_in += tokens_in
            total_out += tokens_out

    total_cost = estimate_cost(total_in, total_out, "")
    return {
        "total_tokens_in": total_in,
        "total_tokens_out": total_out,
        "total_tokens": total_in + total_out,
        "estimated_cost_usd": round(total_cost, 6),
        "by_stage": by_stage,
    }
