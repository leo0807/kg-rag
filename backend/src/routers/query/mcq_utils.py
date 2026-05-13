from __future__ import annotations

import asyncio
import json
import logging
import time

from neo4j import Driver

from ...services.ai.llm_service import get_llm_service
from ...services.context_utils import resolve_retrieval_doc_id
from ...services.infra.cache import set_cached_result
from ...services.qa.mcq_handler import build_mcq_question, solve_mcq_with_elimination
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
        return None
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
) -> list[str] | None:
    mcq = build_mcq_question(question)
    if not mcq:
        return None
    retrieval_doc_id = resolve_retrieval_doc_id(question, doc_hints or [])
    result = await solve_mcq_with_elimination(mcq, driver, get_llm_service(), doc_id=retrieval_doc_id, top_k=max(top_k, 8))
    answer = result.get("answer", "")
    sections = result.get("sources", []) or []
    sources = serialize_sources(sections, {})
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
    if q_emb and answer.strip():
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
    return [
        emit_status_event("🧮 使用排除法分析单选题..."),
        f"data: {json.dumps({'type': 'sources', 'content': sources}, ensure_ascii=False)}\n\n",
        f"data: {json.dumps({'type': 'delta', 'content': answer}, ensure_ascii=False)}\n\n",
        build_metrics_event(latency_ms, latency_ms, len(sections), len(sources)),
        "data: [DONE]\n\n",
    ]
