"""
backend/src/core/observability.py
LLM 可观测性：token 计数、费用估算、Langfuse 追踪、PostgreSQL 用量存储
"""
import asyncio
import base64
import logging
import uuid
from datetime import datetime, timezone

import requests

from .config import settings

logger = logging.getLogger(__name__)

# ── 模型定价表（USD / 1M tokens）────────────────────────────────────────────
# 格式：model_name → {"input": price, "output": price}
MODEL_PRICING: dict[str, dict[str, float]] = {
    # Qwen（硅基流动）
    "Qwen/Qwen2.5-7B-Instruct":        {"input": 0.35,  "output": 0.35},
    "Qwen/Qwen2.5-14B-Instruct":       {"input": 0.70,  "output": 0.70},
    "Qwen/Qwen2.5-32B-Instruct":       {"input": 1.26,  "output": 1.26},
    "Qwen/Qwen2.5-72B-Instruct":       {"input": 4.13,  "output": 4.13},
    "Qwen/Qwen2-72B-Instruct":         {"input": 4.13,  "output": 4.13},
    "Qwen/QwQ-32B":                    {"input": 1.26,  "output": 1.26},
    # DeepSeek
    "deepseek-chat":                   {"input": 0.14,  "output": 0.28},
    "deepseek-reasoner":               {"input": 0.55,  "output": 2.19},
    # Anthropic Claude
    "claude-opus-4-6":                 {"input": 15.00, "output": 75.00},
    "claude-sonnet-4-6":               {"input": 3.00,  "output": 15.00},
    "claude-haiku-4-5-20251001":       {"input": 0.80,  "output": 4.00},
    "claude-3-5-sonnet-20241022":      {"input": 3.00,  "output": 15.00},
    "claude-3-haiku-20240307":         {"input": 0.25,  "output": 1.25},
    # OpenAI
    "gpt-4o":                          {"input": 2.50,  "output": 10.00},
    "gpt-4o-mini":                     {"input": 0.15,  "output": 0.60},
    "gpt-4-turbo":                     {"input": 10.00, "output": 30.00},
    # 本地模型（免费）
    "qwen2.5:7b":                      {"input": 0.0,   "output": 0.0},
    "qwen2.5:14b":                     {"input": 0.0,   "output": 0.0},
    "qwen2.5:32b":                     {"input": 0.0,   "output": 0.0},
    "llama3.1:8b":                     {"input": 0.0,   "output": 0.0},
}

CNY_RATE = 7.25  # USD → CNY 汇率（可通过环境变量覆盖）


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """估算单次 LLM 调用费用（USD）"""
    prices = MODEL_PRICING.get(model)
    if not prices:
        # 未知模型：按通用低价估算（0.5 USD / 1M tokens）
        prices = {"input": 0.5, "output": 0.5}
    cost = (prompt_tokens * prices["input"] + completion_tokens * prices["output"]) / 1_000_000
    return round(cost, 8)


def _langfuse_auth() -> str | None:
    if not settings.LANGFUSE_PUBLIC_KEY or not settings.LANGFUSE_SECRET_KEY:
        return None
    return base64.b64encode(
        f"{settings.LANGFUSE_PUBLIC_KEY}:{settings.LANGFUSE_SECRET_KEY}".encode()
    ).decode()


def _post_langfuse(endpoint: str, payload: dict) -> None:
    auth = _langfuse_auth()
    if not auth:
        return
    try:
        requests.post(
            f"{settings.LANGFUSE_HOST}{endpoint}",
            headers={"Authorization": f"Basic {auth}", "Content-Type": "application/json"},
            json=payload,
            timeout=5,
        )
    except Exception as e:
        logger.debug("Langfuse 推送失败: %s", e)


async def _save_usage_to_db(
    user_id: str,
    department: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    cost_usd: float,
    strategy: str,
    latency_ms: int,
    question_preview: str,
) -> None:
    """异步写入 llm_usage 表（失败静默忽略，不影响主流程）"""
    try:
        from ..db.session import AsyncSessionLocal
        from ..db.models  import LLMUsage
        async with AsyncSessionLocal() as db:
            record = LLMUsage(
                user_id=user_id or None,
                department=department,
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cost_usd=cost_usd,
                strategy=strategy,
                latency_ms=latency_ms,
                question_preview=question_preview[:200],
            )
            db.add(record)
            await db.commit()
    except Exception as e:
        logger.debug("llm_usage 写库失败: %s", e)


def send_generation(
    *,
    name:              str,
    model:             str,
    input_messages:    list[dict],
    output:            str,
    prompt_tokens:     int    = 0,
    completion_tokens: int    = 0,
    latency_ms:        int    = 0,
    strategy:          str    = "",
    user_id:           str    = "",
    department:        str    = "",
    question_preview:  str    = "",
) -> None:
    """
    记录一次 LLM 生成：
    1. 写入 PostgreSQL llm_usage 表（用于费用报表）
    2. 推送 Langfuse generation（用于可观测性仪表盘）
    """
    cost_usd = estimate_cost(model, prompt_tokens, completion_tokens)

    # ── 1. 异步写库（不阻塞调用方）─────────────────────────────────────────
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(_save_usage_to_db(
                user_id=user_id, department=department, model=model,
                prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
                cost_usd=cost_usd, strategy=strategy, latency_ms=latency_ms,
                question_preview=question_preview,
            ))
        else:
            loop.run_until_complete(_save_usage_to_db(
                user_id=user_id, department=department, model=model,
                prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
                cost_usd=cost_usd, strategy=strategy, latency_ms=latency_ms,
                question_preview=question_preview,
            ))
    except Exception as e:
        logger.debug("调度 llm_usage 写库失败: %s", e)

    # ── 2. 推送 Langfuse generation ─────────────────────────────────────────
    trace_id = str(uuid.uuid4())
    now_iso  = datetime.now(timezone.utc).isoformat()

    _post_langfuse("/api/public/ingestion", {
        "batch": [
            {
                "id":        str(uuid.uuid4()),
                "type":      "trace-create",
                "timestamp": now_iso,
                "body": {
                    "id":       trace_id,
                    "name":     name,
                    "metadata": {
                        "user_id":    user_id,
                        "department": department,
                        "strategy":   strategy,
                    },
                    "userId": user_id or None,
                    "tags":   [department] if department else [],
                },
            },
            {
                "id":        str(uuid.uuid4()),
                "type":      "generation-create",
                "timestamp": now_iso,
                "body": {
                    "id":         str(uuid.uuid4()),
                    "traceId":    trace_id,
                    "name":       f"{name}-generation",
                    "model":      model,
                    "input":      input_messages,
                    "output":     output,
                    "startTime":  now_iso,
                    "endTime":    now_iso,
                    "usage": {
                        "promptTokens":     prompt_tokens,
                        "completionTokens": completion_tokens,
                        "totalTokens":      prompt_tokens + completion_tokens,
                        "unit":             "TOKENS",
                    },
                    "metadata": {
                        "latency_ms":   latency_ms,
                        "cost_usd":     cost_usd,
                        "cost_cny":     round(cost_usd * CNY_RATE, 6),
                        "strategy":     strategy,
                        "user_id":      user_id,
                        "department":   department,
                    },
                },
            },
        ]
    })

    logger.info(
        "LLM 用量记录 model=%s prompt=%d completion=%d cost=$%.6f user=%s dept=%s",
        model, prompt_tokens, completion_tokens, cost_usd,
        user_id or "anonymous", department or "-",
    )


# ── 向后兼容：旧版 send_trace 接口 ───────────────────────────────────────────
def send_trace(name: str, input: str, output: str, metadata: dict) -> None:
    """兼容旧调用点。token 数未知时以 0 记录（仅做 Langfuse trace，不计费用）"""
    send_generation(
        name=name,
        model=metadata.get("model", settings.LLM_MODEL),
        input_messages=[{"role": "user", "content": input}],
        output=output,
        latency_ms=metadata.get("latency_ms", 0),
        strategy=metadata.get("strategy", ""),
        user_id=metadata.get("user_id", ""),
        department=metadata.get("department", ""),
        question_preview=input[:200],
    )
