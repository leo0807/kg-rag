"""
非流式查询接口
"""
import logging
import time
from fastapi import Depends, HTTPException, Request
from neo4j import Driver
from sqlalchemy.ext.asyncio import AsyncSession
from ...core.database import get_driver
from ...core.config import settings
from ...core.observability import send_generation
from ...services.ai.llm_service import get_llm_service
from ...services.infra.cache import get_cached_result, set_cached_result
from ...services.runtime.model_settings import load_effective_settings, use_runtime_settings
from ...db.models import User
from .models import QueryRequest, QueryResponse, SourceSection
from .core   import do_retrieval

logger = logging.getLogger(__name__)


async def query_sync(
    request:      Request,
    req:          QueryRequest,
    driver:       Driver = Depends(get_driver),
    current_user: User | None = None,
    db:           AsyncSession | None = None,
):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="question 不能为空")

    effective_settings = await load_effective_settings(db, current_user.id if current_user else None)
    with use_runtime_settings(effective_settings):
        top_k  = req.top_k or 5
        cached = get_cached_result(req.question, req.strategy, top_k)
        if cached:
            return QueryResponse(**cached)

        start = time.time()

        user_id    = current_user.id         if current_user else ""
        department = current_user.department if current_user else ""

        if req.strategy == "multi_hop":
            try:
                from ...services.retrieval.multi_hop import multi_hop_query
                answer, mh_sections, _steps = multi_hop_query(req.question, driver, top_k=top_k)
                sources = [
                    SourceSection(
                        chunk_id=s["chunk_id"], doc_id=s["doc_id"],
                        number=s.get("number") or "", title=s.get("title") or "",
                        score=round(float(s.get("score", 0)), 4),
                        page_idx=s.get("page_idx"),
                        bbox=s.get("bbox"),
                        source_type=s.get("source_type", []),
                        retrieval_trace=s.get("retrieval_trace", []),
                        is_graph_expanded=bool(s.get("is_graph_expanded")),
                        is_vector_hit=bool(s.get("is_vector_hit")),
                        is_fulltext_hit=bool(s.get("is_fulltext_hit")),
                        is_gnn_hit=bool(s.get("is_gnn_hit")),
                    )
                    for s in mh_sections
                ]
                latency_ms = int((time.time() - start) * 1000)
                send_generation(
                    name="graphrag-query", model=get_llm_service().model_name,
                    input_messages=[{"role": "user", "content": req.question}],
                    output=answer, latency_ms=latency_ms, strategy="multi_hop",
                    user_id=user_id, department=department, question_preview=req.question,
                )
                set_cached_result(req.question, req.strategy, top_k,
                                  {"answer": answer, "sources": [s.model_dump() for s in sources]})
                return QueryResponse(answer=answer, sources=sources)
            except Exception as e:
                logger.warning("多跳推理失败，降级: %s", e)

        sections, ft_score_map = do_retrieval(driver, req.question, req.strategy, top_k)
        latency_ms = int((time.time() - start) * 1000)

        prompt_tokens = completion_tokens = 0
        if not sections:
            answer = "在知识库中未找到相关章节，请确认文件已入库。"
        else:
            context = "\n\n".join(
                f"[{s['doc_id']} §{s['number']}] {s['title']}\n{s['content']}"
                for s in sections
            )
            try:
                from ...services.ai.llm import generate_answer_with_usage
                answer, usage = generate_answer_with_usage(
                    question=req.question, context=context, history=req.history,
                )
                prompt_tokens     = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)
            except Exception as e:
                logger.warning("LLM 失败: %s", e)
                answer = f"检索到 {len(sections)} 个相关章节：\n\n{context[:2000]}"

        sources = [
            SourceSection(
                chunk_id=s["chunk_id"], doc_id=s["doc_id"],
                number=s["number"] or "", title=s["title"] or "",
                score=round(s.get("rerank_score") or ft_score_map.get(s["chunk_id"], 0.0), 4),
                page_idx=s.get("page_idx"),
                bbox=s.get("bbox"),
                source_type=s.get("source_type", []),
                retrieval_trace=s.get("retrieval_trace", []),
                is_graph_expanded=bool(s.get("is_graph_expanded")),
                is_vector_hit=bool(s.get("is_vector_hit")),
                is_fulltext_hit=bool(s.get("is_fulltext_hit")),
                is_gnn_hit=bool(s.get("is_gnn_hit")),
            )
            for s in sections
        ]

        send_generation(
            name="graphrag-query", model=get_llm_service().model_name,
            input_messages=[{"role": "user", "content": req.question}],
            output=answer, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
            latency_ms=latency_ms, strategy=req.strategy,
            user_id=user_id, department=department, question_preview=req.question,
        )
        set_cached_result(req.question, req.strategy, top_k,
                          {"answer": answer, "sources": [s.model_dump() for s in sources]})
        return QueryResponse(answer=answer, sources=sources)
