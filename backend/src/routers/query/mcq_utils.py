from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncGenerator

from neo4j import Driver

from ...services.ai.llm_service import get_llm_service
from ...services.context_utils import resolve_retrieval_doc_id
from ...services.infra.cache import set_cached_result
from ...services.qa.mcq_handler import build_mcq_question, solve_mcq_with_elimination
from ...services.qa.mcq_elimination import solve_mcq_streaming
from ...routers.query.models import QueryResponse
from ...routers.query.query_utils import emit_generation_record, log_source_doc_ids, sections_to_sources
from ...routers.query.stream_utils import build_metrics_event, emit_status_event, serialize_sources

logger = logging.getLogger(__name__)


async def maybe_answer_mcq_sync(
    question: str,
    strategy: str,
    top_k: int,
    driver: Driver,
    user_id: str,
    department: str,
    doc_hints: list[str] | None = None,
) -> QueryResponse | None:
    mcq = build_mcq_question(question)
    if not mcq:
        return
    start = time.time()
    retrieval_doc_id = resolve_retrieval_doc_id(question, doc_hints or [])
    result = await solve_mcq_with_elimination(mcq, driver, get_llm_service(), doc_id=retrieval_doc_id, top_k=max(top_k, 8))
    answer = result.get("answer", "")
    sections = result.get("sources", []) or []
    sources = sections_to_sources(sections, {})
    log_source_doc_ids("MCQ排除法", sections)
    latency_ms = int((time.time() - start) * 1000)
    emit_generation_record(
        strategy=strategy,
        question=question,
        answer=answer,
        latency_ms=latency_ms,
        user_id=user_id,
        department=department,
        model_name=get_llm_service().model_name,
    )
    set_cached_result(
        question,
        strategy,
        top_k,
        {"answer": answer, "sources": [s.model_dump() for s in sources]},
    )
    return QueryResponse(answer=answer, sources=sources)


async def maybe_answer_mcq_stream(
    question: str,
    strategy: str,
    top_k: int,
    driver: Driver,
    user_id: str,
    department: str,
    t_start: float,
    doc_hints: list[str] | None = None,
    q_emb: list[float] | None = None,
) -> AsyncGenerator[str, None] | None:
    mcq = build_mcq_question(question)
    if not mcq:
        return
    retrieval_doc_id = resolve_retrieval_doc_id(question, doc_hints or [])
    answer = ""
    sections: list[dict] = []
    sources: list[dict] = []
    yield emit_status_event("🧮 识别为选择题，正在解析选项...")
    async for item in solve_mcq_streaming(mcq, driver, get_llm_service(), doc_id=retrieval_doc_id, top_k=max(top_k, 8)):
        if isinstance(item, dict):
            payload = dict(item)
            if payload.get("type") == "sources":
                sections = payload.get("content") or []
                sources = serialize_sources(sections, {})
                payload["content"] = sources
            elif payload.get("type") == "mcq_answer":
                answer = str(payload.get("content", ""))
            elif payload.get("type") == "answer_meta":
                meta = payload.get("content") or {}
                answer = str(meta.get("answer", ""))
            elif payload.get("type") == "text":
                payload["type"] = "delta"
            elif payload.get("type") == "done":
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                break
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        elif isinstance(item, str) and item.strip():
            yield f"data: {json.dumps({'type': 'delta', 'content': item}, ensure_ascii=False)}\n\n"
    if sections:
        log_source_doc_ids("MCQ排除法", sections)
    latency_ms = int((time.time() - t_start) * 1000)
    emit_generation_record(
        strategy=strategy,
        question=question,
        answer=answer,
        latency_ms=latency_ms,
        user_id=user_id,
        department=department,
        model_name=get_llm_service().model_name,
    )
    if q_emb and answer:
        try:
            from ...services import semantic_cache
            doc_ids = list({s["doc_id"] for s in sources if s.get("doc_id")})
            await asyncio.to_thread(
                semantic_cache.store,
                q_emb, strategy or "parallel", answer,
                sources, question[:200], doc_ids,
            )
        except Exception as exc:
            logger.debug("MCQ 语义缓存写入失败（跳过）: %s", exc)
    yield build_metrics_event(latency_ms, latency_ms, len(sections), len(sources))
    yield "data: [DONE]\n\n"
