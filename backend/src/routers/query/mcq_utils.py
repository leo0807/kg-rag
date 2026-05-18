from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncGenerator

from neo4j import Driver

from ...routers.query.models import QueryResponse
from ...routers.query.query_utils import emit_generation_record, log_source_doc_ids, sections_to_sources
from ...services.ai.errors import LLMError
from ...routers.query.stream_utils import build_metrics_event, serialize_sources
from ...routers.query.stream_utils import _error_event
from ...services.ai.llm_service import get_llm_service
from ...services.context_utils import resolve_retrieval_doc_id
from ...services.infra.cache import set_cached_result
from ...services.qa.mcq_handler import build_mcq_question
from ...services.qa.mcq.router import route_mcq
from ...services.qa.mcq.formatter import format_mcq_answer_md

logger = logging.getLogger(__name__)


def _format_mcq_answer(meta: dict, options: dict[str, str]) -> str:
    payload = meta.get('parsed') if isinstance(meta.get('parsed'), dict) else meta
    payload = payload if isinstance(payload, dict) else meta
    payload = {**payload, 'predicted': meta.get('predicted') or payload.get('predicted') or payload.get('final_answer')}
    return format_mcq_answer_md(payload, options)


async def answer_mcq_sync(
    mcq,
    strategy: str,
    top_k: int,
    driver: Driver,
    user_id: str,
    department: str,
    llm=None,
    reranker=None,
    doc_hints: list[str] | None = None,
) -> dict | None:
    retrieval_doc_id = resolve_retrieval_doc_id(mcq.stem, doc_hints or [])
    solver = route_mcq(mcq, driver, llm or get_llm_service(), reranker)
    result = await solver.solve(mcq, doc_id=retrieval_doc_id, top_k=max(top_k, 8))
    answer = result.get('answer', '')
    sections = result.get('sources', []) or []
    sources = sections_to_sources(sections, {})
    log_source_doc_ids('MCQ路由', sections)
    latency_ms = int((time.time() - result.get('start_time', time.time())) * 1000) if result.get('start_time') else 0
    emit_generation_record(
        strategy=strategy,
        question=mcq.stem,
        answer=answer,
        latency_ms=latency_ms,
        user_id=user_id,
        department=department,
        model_name=get_llm_service().model_name,
    )
    set_cached_result(
        mcq.stem,
        strategy,
        top_k,
        {'answer': answer, 'sources': [s.model_dump() for s in sources]},
    )
    answer_meta = result.get('answer_meta') or {}
    mcq_meta = answer_meta.get('parsed') if isinstance(answer_meta.get('parsed'), dict) else (answer_meta or None)
    mcq_type = None
    if isinstance(mcq_meta, dict):
        mcq_type = mcq_meta.get('mcq_type') or mcq_meta.get('type')
        mcq_meta = {**mcq_meta, 'predicted': mcq_meta.get('predicted') or mcq_meta.get('final_answer') or answer}
    mcq_type = mcq_type or result.get('mcq_type')
    if not answer and isinstance(mcq_meta, dict):
        answer = _format_mcq_answer(mcq_meta, mcq.options)
    return {
        'type': 'answer',
        'answer': answer,
        'sources': sources,
        'mcq_meta': mcq_meta,
        'mcq_type': mcq_type,
    }


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
    payload = await answer_mcq_sync(
        mcq,
        strategy,
        top_k,
        driver,
        user_id,
        department,
        llm=get_llm_service(),
        doc_hints=doc_hints,
    )
    return QueryResponse(**payload)


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
    solver = route_mcq(mcq, driver, get_llm_service())
    sections: list[dict] = []
    sources: list[dict] = []
    final_answer = ''
    predicted = ''
    async for event in solver.solve_streaming(mcq, doc_id=retrieval_doc_id, top_k=max(top_k, 8)):
        etype = event.get('type')
        if etype == 'stage':
            yield f"data: {json.dumps({'type': 'stage', 'content': event.get('content')}, ensure_ascii=False)}\n\n"
            continue
        if etype == 'sources':
            sections = event.get('items') or []
            sources = serialize_sources(sections, {})
            log_source_doc_ids('MCQ路由', sections)
            yield f"data: {json.dumps({'type': 'sources', 'content': sources}, ensure_ascii=False)}\n\n"
            continue
        if etype == 'delta':
            delta = str(event.get('content') or '')
            if delta:
                yield f"data: {json.dumps({'type': 'delta', 'content': delta}, ensure_ascii=False)}\n\n"
            continue
        if etype == 'answer_meta':
            predicted = str(event.get('predicted') or '')
            final_answer = str(event.get('formatted_answer') or event.get('answer') or '')
            yield f"data: {json.dumps({'type': 'mcq_answer', 'content': predicted}, ensure_ascii=False)}\n\n"
            continue
        if etype == 'error':
            yield f"data: {json.dumps({'type': 'error', 'code': event.get('code') or 'internal_error', 'status_code': event.get('status_code'), 'message': str(event.get('message') or 'AI 服务异常，请联系管理员')}, ensure_ascii=False)}\n\n"
            continue
        if etype == 'parse_failed':
            message = str(event.get('reason') or 'MCQ 解析失败')
            yield f"data: {json.dumps({'type': 'error', 'code': 'mcq_parse_failed', 'message': message}, ensure_ascii=False)}\n\n"
            continue
        if etype == 'done':
            continue

    latency_ms = int((time.time() - t_start) * 1000)
    emit_generation_record(
        strategy=strategy,
        question=question,
        answer=final_answer,
        latency_ms=latency_ms,
        user_id=user_id,
        department=department,
        model_name=get_llm_service().model_name,
    )
    if q_emb and final_answer.strip():
        try:
            from ...services import semantic_cache
            doc_ids = list({s['doc_id'] for s in sources if s.get('doc_id')})
            await asyncio.to_thread(
                semantic_cache.store,
                q_emb, strategy or 'parallel', final_answer,
                sources, question[:200], doc_ids,
            )
        except Exception as exc:
            logger.debug('MCQ 语义缓存写入失败（跳过）: %s', exc)
    yield build_metrics_event(latency_ms, latency_ms, len(sections), len(sources))
    yield 'data: [DONE]\n\n'


async def forward_mcq_stream(
    mcq_events: AsyncGenerator[str, None],
) -> AsyncGenerator[str, None]:
    try:
        async for event in mcq_events:
            yield event
    except LLMError as e:
        logger.warning("MCQ 流式 LLMError: %s", e)
        yield _error_event(e)
        yield 'data: [DONE]\n\n'
    except Exception as e:
        logger.exception("MCQ 流式推理失败")
        yield _error_event(e)
        yield 'data: [DONE]\n\n'
