"""
非流式查询接口
"""
import logging
import time
from fastapi import Depends, HTTPException, Request
from neo4j import Driver
from ...core.database import get_driver
from ...core.observability import send_trace
from ...services.cache import get_cached_result, set_cached_result
from .models import QueryRequest, QueryResponse, SourceSection
from .core   import do_retrieval

logger = logging.getLogger(__name__)


async def query_sync(
    request: Request,
    req:     QueryRequest,
    driver:  Driver = Depends(get_driver),
):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="question 不能为空")

    top_k  = req.top_k or 5
    cached = get_cached_result(req.question, req.strategy, top_k)
    if cached:
        return QueryResponse(**cached)

    start = time.time()

    if req.strategy == "multi_hop":
        try:
            from ...services.multi_hop import multi_hop_query
            answer, mh_sections = multi_hop_query(req.question, driver, top_k=top_k)
            sources = [
                SourceSection(
                    chunk_id=s["chunk_id"], doc_id=s["doc_id"],
                    number=s.get("number") or "", title=s.get("title") or "",
                    score=round(float(s.get("score", 0)), 4),
                )
                for s in mh_sections
            ]
            latency_ms = int((time.time() - start) * 1000)
            send_trace(name="graphrag-query", input=req.question, output=answer,
                       metadata={"strategy": "multi_hop", "latency_ms": latency_ms})
            set_cached_result(req.question, req.strategy, top_k,
                              {"answer": answer, "sources": [s.model_dump() for s in sources]})
            return QueryResponse(answer=answer, sources=sources)
        except Exception as e:
            logger.warning("多跳推理失败，降级: %s", e)

    sections, ft_score_map = do_retrieval(driver, req.question, req.strategy, top_k)
    latency_ms = int((time.time() - start) * 1000)

    if not sections:
        answer = "在知识库中未找到相关章节，请确认文件已入库。"
    else:
        context = "\n\n".join(
            f"[{s['doc_id']} §{s['number']}] {s['title']}\n{s['content']}"
            for s in sections
        )
        try:
            from ...services.llm import generate_answer
            answer = generate_answer(question=req.question, context=context)
        except Exception as e:
            logger.warning("LLM 失败: %s", e)
            answer = f"检索到 {len(sections)} 个相关章节：\n\n{context[:2000]}"

    sources = [
        SourceSection(
            chunk_id=s["chunk_id"], doc_id=s["doc_id"],
            number=s["number"] or "", title=s["title"] or "",
            score=round(s.get("rerank_score") or ft_score_map.get(s["chunk_id"], 0.0), 4),
        )
        for s in sections
    ]

    send_trace(name="graphrag-query", input=req.question, output=answer,
               metadata={"strategy": req.strategy, "latency_ms": latency_ms})
    set_cached_result(req.question, req.strategy, top_k,
                      {"answer": answer, "sources": [s.model_dump() for s in sources]})
    return QueryResponse(answer=answer, sources=sources)