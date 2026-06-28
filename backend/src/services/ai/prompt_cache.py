"""
Anthropic Prompt Caching support.

Wraps messages with cache_control: {"type": "ephemeral"} for:
  - System prompt (role/format instructions)
  - Long document contexts (hot sections)
  - Few-shot examples

Tracks cache_read_tokens / cache_write_tokens in llm_usage table.
See: https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching
"""
from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)

CACHE_THRESHOLD_TOKENS = 1024  # min tokens to cache (Anthropic requirement)


def apply_cache_control(messages: list[dict],
                         cache_system: bool = True,
                         cache_threshold: int = CACHE_THRESHOLD_TOKENS) -> list[dict]:
    """
    Add cache_control to eligible message parts.

    Marks the last user/assistant turn's content blocks that meet
    the 1024-token threshold for caching. Anthropic Claude API only.

    Args:
        messages: OpenAI-format message list
        cache_system: Whether to cache the system prompt
        cache_threshold: Minimum estimated tokens to apply caching

    Returns:
        Messages with cache_control annotations on eligible blocks.
    """
    result = []
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")

        if role == "system" and cache_system:
            # System prompt → cache if long enough
            if isinstance(content, str):
                est_tokens = len(content) // 4
                if est_tokens >= cache_threshold:
                    result.append({
                        "role": "system",
                        "content": [
                            {
                                "type": "text",
                                "text": content,
                                "cache_control": {"type": "ephemeral"},
                            }
                        ],
                    })
                    continue

        elif role == "user" and isinstance(content, str):
            # Long context blocks (e.g. retrieved sections embedded in prompt)
            est_tokens = len(content) // 4
            if est_tokens >= cache_threshold:
                result.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": content,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                })
                continue

        result.append(msg)
    return result


def extract_cache_stats(response_headers: dict) -> dict[str, int]:
    """
    Extract cache read/write token counts from Anthropic response headers.
    Use with `response.usage` from anthropic SDK.
    """
    return {
        "cache_read_tokens": int(response_headers.get("x-cache-read-input-tokens", 0)),
        "cache_write_tokens": int(response_headers.get("x-cache-creation-input-tokens", 0)),
    }


def build_cached_system_prompt(base_instructions: str,
                                 few_shot_examples: list[dict] | None = None) -> list[dict]:
    """
    Build a cached system prompt with optional few-shot examples.
    The entire block is marked for caching so all requests share it.
    """
    content_parts: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": base_instructions,
        }
    ]

    if few_shot_examples:
        examples_text = "\n\n".join(
            f"示例 {i+1}:\n问题: {ex.get('question', '')}\n答案: {ex.get('answer', '')}"
            for i, ex in enumerate(few_shot_examples)
        )
        content_parts.append({
            "type": "text",
            "text": f"\n\n以下是参考示例：\n{examples_text}",
        })

    # Mark last block for caching (Anthropic requires cache_control on last block)
    content_parts[-1]["cache_control"] = {"type": "ephemeral"}

    return [{"role": "system", "content": content_parts}]


async def log_cache_usage(prompt_tokens: int, cache_read: int,
                           cache_write: int, user_id: str,
                           model: str, cost_usd: float) -> None:
    """Persist cache usage stats to llm_usage table."""
    try:
        import asyncpg
        from ...core.config import settings
        dsn = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
        conn = await asyncpg.connect(dsn)
        await conn.execute(
            """
            INSERT INTO llm_usage
                (user_id, model, prompt_tokens, completion_tokens,
                 cache_read_tokens, cache_write_tokens, cost_usd, created_at)
            VALUES ($1, $2, $3, 0, $4, $5, $6, NOW())
            """,
            user_id, model, prompt_tokens, cache_read, cache_write, cost_usd,
        )
        await conn.close()
    except Exception as exc:
        log.debug("Cache usage logging failed: %s", exc)
