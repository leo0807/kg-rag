from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING

from .ai.llm_service import get_llm_service
from .infra.cache import set_cached_result
from .query_text2cypher import resolve_count_question
from ..routers.query.query_utils import emit_generation_record
from ..routers.query.models import QueryMetrics, QueryResponse

if TYPE_CHECKING:
    from neo4j import Driver


async def maybe_build_total_cps_count_response(
    question: str,
    strategy: str,
    top_k: int,
    driver: Driver,
    user_id: str,
    department: str,
) -> QueryResponse | None:
    result = await asyncio.to_thread(resolve_count_question, question, driver)
    if not result:
        return None
    answer = result["answer"]
    emit_generation_record(
        strategy=strategy,
        question=question,
        answer=answer,
        latency_ms=0,
        user_id=user_id,
        department=department,
        model_name=get_llm_service().model_name,
    )
    set_cached_result(
        question,
        strategy,
        top_k,
        {"answer": answer, "sources": [], "images": [], "expansion_info": []},
    )
    return QueryResponse(
        answer=answer,
        sources=[],
        images=[],
        expansion_info=[],
        metrics=QueryMetrics(
            total_ms=0,
            stages={"统计": 0},
            tokens={"prompt": 0, "completion": 0, "total": 0},
            cost_usd=0.0,
            candidates_retrieved=0,
            candidates_after_rerank=0,
        ),
    )


async def maybe_build_total_cps_count_events(
    question: str,
    strategy: str,
    top_k: int,
    driver: Driver,
    user_id: str,
    department: str,
) -> list[str] | None:
    response = await maybe_build_total_cps_count_response(
        question, strategy, top_k, driver, user_id, department
    )
    if not response:
        return None
    count_match = re.search(r"共\s*(\d+)\s*(?:本|个|张)", response.answer)
    found = int(count_match.group(1)) if count_match else 0
    label = "CPS 文档总数"
    title = "Document 节点"
    if "章节" in response.answer:
        label = "章节数"
        title = "Section 节点"
    elif "图片" in response.answer:
        label = "图片数"
        title = "Image 节点"
    elif "表格" in response.answer:
        label = "表格数"
        title = "Table 节点"
    return [
        f"data: {{\"type\": \"steps\", \"content\": [{{\"hop\": 1, \"query\": \"统计 {label}\", \"found\": {found}, \"titles\": [\"{title}\"]}}]}}\n\n",
        f"data: {{\"type\": \"status\", \"content\": \"正在统计 {label}...\"}}\n\n",
        f"data: {{\"type\": \"delta\", \"content\": {response.answer!r}}}\n\n",
        "data: [DONE]\n\n",
    ]
