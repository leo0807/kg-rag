from __future__ import annotations

import json
import logging
import time

from ...core.observability import send_generation
from ...services.infra.cache import set_cached_result
from ...services.retrieval.compare_query import run_compare_query
from ...services.retrieval.compare_summary import summarize_compare_answer
from .stream_utils import _emit_follow_ups, emit_status_event, serialize_sources

logger = logging.getLogger(__name__)


async def build_compare_stream_events(
    *,
    question: str,
    driver,
    top_k: int,
    t_start: float,
    user_id: str,
    department: str,
    strategy: str,
    use_hyde: bool = False,
    hyde_alpha: float = 0.5,
) -> list[str] | None:
    compare_result = await run_compare_query(
        driver,
        question,
        strategy,
        top_k,
        use_hyde,
        hyde_alpha,
    )
    if not compare_result:
        return None

    events: list[str] = []
    sources = serialize_sources(
        compare_result.get("sections", []),
        compare_result.get("ft_score_map", {}),
    )
    events.append(
        f"data: {json.dumps({'type': 'sources', 'content': sources}, ensure_ascii=False)}\n\n"
    )
    images = compare_result.get("images", [])
    if images:
        events.append(
            f"data: {json.dumps({'type': 'images', 'content': images}, ensure_ascii=False)}\n\n"
    )
    logger.info(
        "[compare] sources=%s",
        sorted({s.get("doc_id", "") for s in compare_result.get("sections", []) if s.get("doc_id")}),
    )
    events.append(emit_status_event("正在生成对比答案..."))
    answer = await summarize_compare_answer(
        question,
        compare_result.get("sections", []),
        compare_result.get("images", []),
    )
    for char in answer:
        events.append(
            f"data: {json.dumps({'type': 'delta', 'content': char}, ensure_ascii=False)}\n\n"
        )

    latency_ms = int((time.time() - t_start) * 1000)
    send_generation(
        name="graphrag-stream",
        model="agent-compare",
        input_messages=[{"role": "user", "content": question}],
        output=answer,
        latency_ms=latency_ms,
        strategy=strategy,
        user_id=user_id,
        department=department,
        question_preview=question,
    )
    set_cached_result(
        question,
        strategy,
        top_k,
        {
            "answer": answer,
            "sources": [s for s in sources],
            "images": compare_result.get("images", []),
        },
    )
    events.append(
        f"data: {json.dumps({'type': 'metrics', 'content': {'total_ms': latency_ms, 'stages': {}, 'tokens': {}, 'cost_usd': 0.0, 'candidates_retrieved': len(sources), 'candidates_after_rerank': len(sources)}}, ensure_ascii=False)}\n\n"
    )
    followups = await _emit_follow_ups(
        question,
        answer,
        [s.get("doc_id") for s in compare_result.get("sections", []) if s.get("doc_id")],
    )
    if followups:
        events.append(f"data: {followups}\n\n")
    events.append("data: [DONE]\n\n")
    return events
