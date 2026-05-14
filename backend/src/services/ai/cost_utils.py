from __future__ import annotations

_MODEL_PRICE: dict[str, tuple[float, float]] = {
    "gpt-4o": (0.005, 0.015),
    "gpt-4o-mini": (0.00015, 0.0006),
    "gpt-4-turbo": (0.01, 0.03),
    "claude-3-5-sonnet": (0.003, 0.015),
    "claude-3-haiku": (0.00025, 0.00125),
    "qwen2.5-7b": (0.0, 0.0),
    "qwen/qwen2.5-7b": (0.0, 0.0),
    "qwen-plus": (0.0004, 0.0012),
    "deepseek-chat": (0.00014, 0.00028),
    "deepseek-v3": (0.00027, 0.0011),
}


def calc_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    key = (model or "").lower()
    for pattern, (inp_price, out_price) in _MODEL_PRICE.items():
        if pattern in key:
            return (prompt_tokens / 1000) * inp_price + (completion_tokens / 1000) * out_price
    return 0.0
