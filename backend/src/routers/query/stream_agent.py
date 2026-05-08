from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import AsyncGenerator

from ...core.observability import send_generation
from ...services.agent.agent_executor import AgentExecutor
from ...services.agent.tool_executor import ToolExecutor
from ...services.ai.llm import clean_llm_response
from ...services.ai.llm_service import get_llm_service
from ...services.infra.cache import set_cached_result
from .stream_utils import _emit_follow_ups

logger = logging.getLogger(__name__)


def _to_sources(sections: list[dict]) -> list[dict]:
    return [
        {
            "chunk_id": s["chunk_id"],
            "doc_id": s["doc_id"],
            "number": s.get("number") or "",
            "title": s.get("title") or "",
            "score": round(float(s.get("score") or s.get("rrf_score") or 0.0), 4),
            "page_idx": s.get("page_idx"),
            "bbox": s.get("bbox"),
            "source_type": s.get("source_type", []),
            "retrieval_trace": s.get("retrieval_trace", []),
            "is_graph_expanded": bool(s.get("is_graph_expanded")),
            "is_vector_hit": bool(s.get("is_vector_hit")),
            "is_fulltext_hit": bool(s.get("is_fulltext_hit")),
            "is_gnn_hit": bool(s.get("is_gnn_hit")),
        }
        for s in sections
    ]


async def stream_agent_query(
    question: str,
    driver,
    top_k: int,
    t_start: float,
    user_id: str,
    department: str,
) -> AsyncGenerator[str, None]:
    yield f"data: {json.dumps({'type': 'status', 'content': 'Agent 推理中...'}, ensure_ascii=False)}\n\n"
    executor = AgentExecutor(get_llm_service(), ToolExecutor(driver))
    queue: asyncio.Queue[dict] = asyncio.Queue()

    async def emit_event(payload: dict) -> None:
        await queue.put(payload)

    async def run_agent() -> None:
        try:
            result = await executor.run(question, emit_event=emit_event)
            await queue.put({"type": "agent_done", "result": result})
        except Exception as exc:
            await queue.put({"type": "agent_error", "error": str(exc)})

    task = asyncio.create_task(run_agent())
    result: dict | None = None
    agent_steps: list[dict] = []
    while True:
        event = await queue.get()
        if event.get("type") == "agent_done":
            result = event.get("result", {})
            break
        if event.get("type") == "agent_error":
            task.cancel()
            raise RuntimeError(event.get("error") or "Agent 执行失败")
        yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    await task
    result = result or {}
    agent_steps = result.get("agent_steps", [])
    images = result.get("images", []) or []

    answer = clean_llm_response(result.get("answer", ""))
    sources = _to_sources(result.get("sources", []))
    yield f"data: {json.dumps({'type': 'sources', 'content': sources}, ensure_ascii=False)}\n\n"
    if agent_steps:
        yield f"data: {json.dumps({'type': 'agent_steps', 'content': agent_steps}, ensure_ascii=False)}\n\n"
    for char in answer:
        yield f"data: {json.dumps({'type': 'delta', 'content': char}, ensure_ascii=False)}\n\n"

    latency_ms = int((time.time() - t_start) * 1000)
    send_generation(
        name="graphrag-stream",
        model=get_llm_service().model_name,
        input_messages=[{"role": "user", "content": question}],
        output=answer,
        latency_ms=latency_ms,
        strategy="agent",
        user_id=user_id,
        department=department,
        question_preview=question,
    )
    set_cached_result(
        question,
        "agent",
        top_k,
        {
            "answer": answer,
            "sources": sources,
            "images": images,
            "iterations": result.get("iterations"),
            "strategy_used": result.get("strategy_used", "agent"),
            "agent_steps": agent_steps,
        },
    )
    yield f"data: {json.dumps({'type': 'metrics', 'content': {'total_ms': latency_ms, 'stages': {}, 'tokens': {}, 'cost_usd': 0.0, 'candidates_retrieved': len(sources), 'candidates_after_rerank': len(sources)}}, ensure_ascii=False)}\n\n"
    if followups := await _emit_follow_ups(question, answer):
        yield f"data: {followups}\n\n"
    yield "data: [DONE]\n\n"
