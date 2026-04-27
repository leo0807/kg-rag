"""
src/routers/query/compare.py
四策略并行对比查询 — POST /api/query/compare
"""
import asyncio
import time
import logging
from fastapi import Depends
from neo4j import Driver
from sqlalchemy.ext.asyncio import AsyncSession
from ...core.database import get_driver
from ...services.ai.llm_service import get_llm_service, LLMError
from ...services.runtime.model_settings import load_effective_settings, use_runtime_settings
from ...db.models import User
from .models import QueryRequest
from .core import do_retrieval

logger = logging.getLogger(__name__)

COMPARE_STRATEGIES = ["parallel", "sequential", "graph_augmented", "multi_hop", "hybrid_es"]

STRATEGY_LABELS = {
    "parallel":        "并行检索",
    "sequential":      "顺序检索",
    "graph_augmented": "图谱增强",
    "multi_hop":       "多跳推理",
    "hybrid_es":       "ES 混合检索",
}


async def _run_strategy(driver: Driver, question: str, strategy: str, top_k: int) -> dict:
    t0 = time.time()
    try:
        if strategy == "multi_hop":
            from ...services.retrieval.multi_hop import multi_hop_query
            answer, sections, _ = await asyncio.to_thread(
                multi_hop_query, question, driver, top_k=top_k
            )
            sources = [
                {
                    "chunk_id": s["chunk_id"], "doc_id": s["doc_id"],
                    "number":   s.get("number") or "", "title": s.get("title") or "",
                    "score":    round(float(s.get("score", 0)), 4),
                }
                for s in sections
            ]
        else:
            sections, ft_score_map = await asyncio.to_thread(
                do_retrieval, driver, question, strategy, top_k
            )
            sources = [
                {
                    "chunk_id": s["chunk_id"], "doc_id": s["doc_id"],
                    "number":   s.get("number") or "", "title": s.get("title") or "",
                    "score":    round(
                        s.get("rerank_score") or ft_score_map.get(s["chunk_id"], 0.0), 4
                    ),
                }
                for s in sections
            ]
            context = "\n\n".join(
                f"[{s['doc_id']} §{s['number']}] {s['title']}\n{s['content']}"
                for s in sections
            )
            messages = [
                {
                    "role":    "system",
                    "content": "你是一个航空制造工艺规范专家助手。请根据提供的规范内容，用中文准确回答问题。",
                },
                {
                    "role":    "user",
                    "content": f"## 相关规范内容\n\n{context}\n\n## 问题\n\n{question}",
                },
            ]
            answer = await asyncio.to_thread(get_llm_service().chat, messages)

        return {
            "strategy":   strategy,
            "label":      STRATEGY_LABELS[strategy],
            "answer":     answer,
            "sources":    sources,
            "latency_ms": int((time.time() - t0) * 1000),
            "error":      None,
        }
    except Exception as e:
        logger.warning("compare strategy %s failed: %s", strategy, e)
        llm_err = e if isinstance(e, LLMError) else None
        return {
            "strategy":   strategy,
            "label":      STRATEGY_LABELS[strategy],
            "answer":     None,
            "sources":    [],
            "latency_ms": int((time.time() - t0) * 1000),
            "error": {
                "code":        llm_err.code        if llm_err else "unknown_error",
                "message":     llm_err.message     if llm_err else str(e),
                "status_code": llm_err.status_code if llm_err else None,
                "endpoint":    llm_err.endpoint    if llm_err else "",
            },
        }


async def query_compare(
    req:    QueryRequest,
    driver: Driver = Depends(get_driver),
    current_user: User | None = None,
    db: AsyncSession | None = None,
):
    top_k = req.top_k or 5
    effective_settings = await load_effective_settings(db, current_user.id if current_user else None)
    with use_runtime_settings(effective_settings):
        tasks = [_run_strategy(driver, req.question, s, top_k) for s in COMPARE_STRATEGIES]
        results = await asyncio.gather(*tasks)
        return {"question": req.question, "results": list(results)}
