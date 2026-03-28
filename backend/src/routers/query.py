import logging
import time
from fastapi import APIRouter, Depends, HTTPException, Request
from neo4j import Driver
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address
from ..core.database import get_driver
from ..core.observability import send_trace

logger   = logging.getLogger(__name__)
router   = APIRouter(prefix="/api", tags=["query"])
limiter  = Limiter(key_func=get_remote_address)


class QueryRequest(BaseModel):
    question: str
    strategy: str = "parallel"
    top_k:    int = 5


class SourceSection(BaseModel):
    chunk_id: str
    doc_id:   str
    number:   str
    title:    str
    score:    float


class QueryResponse(BaseModel):
    answer:  str
    sources: list[SourceSection]


def rrf_fusion(
    fulltext_ids: list[str],
    vector_ids:   list[str],
    k:            int = 60,
) -> list[str]:
    """
    Reciprocal Rank Fusion 融合两个排序列表
    RRF score = 1/(k + rank)，k=60 是经验值
    """
    scores: dict[str, float] = {}

    for rank, chunk_id in enumerate(fulltext_ids, start=1):
        scores[chunk_id] = scores.get(chunk_id, 0) + 1 / (k + rank)

    for rank, chunk_id in enumerate(vector_ids, start=1):
        scores[chunk_id] = scores.get(chunk_id, 0) + 1 / (k + rank)

    return sorted(scores, key=lambda x: scores[x], reverse=True)


def get_section_details(driver: Driver, chunk_ids: list[str]) -> list[dict]:
    """从 Neo4j 批量获取章节详情"""
    if not chunk_ids:
        return []
    with driver.session() as session:
        result = session.run("""
            UNWIND $chunk_ids AS cid
            MATCH (s:Section {chunk_id: cid})
            RETURN s.chunk_id       AS chunk_id,
                   s.doc_id         AS doc_id,
                   s.section_number AS number,
                   s.title          AS title,
                   s.content        AS content
        """, chunk_ids=chunk_ids)
        records = {r["chunk_id"]: dict(r) for r in result}
    # 保持原始顺序
    return [records[cid] for cid in chunk_ids if cid in records]


@router.post("/query", response_model=QueryResponse)
@limiter.limit("30/minute")
async def query(
    request:  Request,
    req:      QueryRequest,
    driver:   Driver = Depends(get_driver),
):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="question 不能为空")

    top_k = req.top_k or 5
    start = time.time()

    # ── 全文检索 ──────────────────────────────
    with driver.session() as session:
        ft_result = session.run("""
            CALL db.index.fulltext.queryNodes(
                'cps_fulltext_index', $question
            ) YIELD node, score
            RETURN node.chunk_id AS chunk_id, score
            ORDER BY score DESC
            LIMIT $top_k
        """, question=req.question, top_k=top_k * 2)
        ft_records  = [dict(r) for r in ft_result]
        ft_ids      = [r["chunk_id"] for r in ft_records]
        ft_score_map = {r["chunk_id"]: r["score"] for r in ft_records}

    # ── 向量检索 ──────────────────────────────
    vector_ids = []
    if req.strategy in ("parallel", "graph_augmented"):
        try:
            from ..services.embedder      import embed_query
            from ..services.milvus_store  import search_sections
            query_vec   = embed_query(req.question)
            vec_results = search_sections(query_vec, top_k=top_k * 2)
            vector_ids  = [r["chunk_id"] for r in vec_results]
        except Exception as e:
            logger.warning("向量检索失败，降级到全文检索: %s", e)

    # ── RRF 融合 ──────────────────────────────
    if req.strategy == "parallel" and vector_ids:
        fused_ids = rrf_fusion(ft_ids, vector_ids)[:top_k]
    else:
        fused_ids = ft_ids[:top_k]

    # ── 获取章节详情 ──────────────────────────
    sections = get_section_details(driver, fused_ids)

    latency_ms = int((time.time() - start) * 1000)

    if not sections:
        answer = "在知识库中未找到相关章节，请确认文件已入库。"
    else:
        context = "\n\n".join(
            f"[{s['doc_id']} §{s['number']}] {s['title']}\n{s['content']}"
            for s in sections[:3]
        )
        answer = f"根据工艺规范知识库，检索到 {len(sections)} 个相关章节：\n\n{context[:2000]}"

    sources = [
        SourceSection(
            chunk_id = s["chunk_id"],
            doc_id   = s["doc_id"],
            number   = s["number"] or "",
            title    = s["title"]  or "",
            score    = round(ft_score_map.get(s["chunk_id"], 0.0), 4),
        )
        for s in sections
    ]

    send_trace(
        name     = "graphrag-query",
        input    = req.question,
        output   = answer,
        metadata = {
            "strategy":    req.strategy,
            "latency_ms":  latency_ms,
            "ft_count":    len(ft_ids),
            "vec_count":   len(vector_ids),
            "fused_count": len(fused_ids),
        },
    )

    return QueryResponse(answer=answer, sources=sources)