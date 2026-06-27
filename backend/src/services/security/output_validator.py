"""
Pydantic-enforced LLM output format validator with auto-retry.

Enforces that every LLM response contains:
  answer     — non-empty string
  sources    — list with at least one item (chunk_id + title)
  confidence — float in [0, 1]

Usage:
    from .output_validator import validate_llm_output, LLMResponse

    # Validate an already-parsed dict:
    response = validate_llm_output(raw_dict)

    # Wrap an LLM call with auto-retry on format failure:
    result = await call_with_format_retry(llm_fn, question, sources, max_retries=3)
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable, Awaitable

from pydantic import BaseModel, Field, field_validator, model_validator

log = logging.getLogger(__name__)


class SourceRef(BaseModel):
    chunk_id: str
    title:    str = ""
    score:    float = 0.0


class LLMResponse(BaseModel):
    """Canonical LLM output schema enforced before returning to user."""

    answer:     str         = Field(..., min_length=1)
    sources:    list[SourceRef] = Field(..., min_length=1)
    confidence: float       = Field(default=0.8, ge=0.0, le=1.0)
    strategy:   str         = ""

    @field_validator("answer")
    @classmethod
    def answer_not_whitespace(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("answer must not be blank")
        return stripped

    @model_validator(mode="after")
    def sources_not_empty(self) -> "LLMResponse":
        if not self.sources:
            raise ValueError("sources list must contain at least one item")
        return self


def validate_llm_output(raw: dict[str, Any]) -> LLMResponse:
    """
    Parse and validate raw LLM output dict.
    Raises pydantic.ValidationError on schema violation.
    """
    # Normalise sources: accept list[str] (chunk_ids) or list[dict]
    sources = raw.get("sources", [])
    if sources and isinstance(sources[0], str):
        raw = {**raw, "sources": [{"chunk_id": s} for s in sources]}
    return LLMResponse.model_validate(raw)


def _build_retry_prompt(question: str, prior_answer: str, errors: str) -> str:
    return (
        f"你的上一次回答格式不符合要求，错误信息：{errors}\n\n"
        f"请重新回答以下问题，必须在 JSON 中包含 answer（字符串）、"
        f"sources（至少一个 {{chunk_id, title}} 对象的列表）、confidence（0-1 浮点）三个字段。\n\n"
        f"问题：{question}\n上次回答：{prior_answer}"
    )


async def call_with_format_retry(
    llm_fn: Callable[..., Awaitable[str]],
    question: str,
    sources: list[dict],
    max_retries: int = 3,
    **llm_kwargs: Any,
) -> LLMResponse:
    """
    Call llm_fn; if output fails LLMResponse validation, retry with error context.

    llm_fn must be async and return a JSON-parseable string.
    """
    last_error = ""
    last_raw = ""
    for attempt in range(max_retries):
        try:
            if attempt == 0:
                raw_text = await llm_fn(question=question, sources=sources, **llm_kwargs)
            else:
                prompt = _build_retry_prompt(question, last_raw, last_error)
                raw_text = await llm_fn(question=prompt, sources=sources, **llm_kwargs)

            last_raw = raw_text
            data = json.loads(raw_text) if raw_text.strip().startswith("{") else {"answer": raw_text, "sources": sources}
            return validate_llm_output(data)

        except (json.JSONDecodeError, ValueError, Exception) as exc:
            last_error = str(exc)
            log.warning("LLM output validation failed (attempt %d/%d): %s",
                        attempt + 1, max_retries, exc)
            if attempt < max_retries - 1:
                await asyncio.sleep(0.5)

    # Final fallback: return best-effort response with low confidence
    log.error("All %d retry attempts failed; returning fallback response", max_retries)
    return LLMResponse(
        answer=last_raw or "无法生成符合格式要求的回答，请重试。",
        sources=[SourceRef(chunk_id=s.get("chunk_id", ""), title=s.get("title", ""))
                 for s in sources[:3]],
        confidence=0.1,
    )
