import logging
import time
from fastapi import APIRouter, Depends, HTTPException, Request
from neo4j import Driver
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address
from ..core.database import get_driver
from ..core.observability import send_trace
from ..services.cache import get_cached_result, set_cached_result

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

    # ── 缓存检查 ──────────────────────────────
    cached = get_cached_result(req.question, req.strategy, top_k)
    if cached:
        return QueryResponse(**cached)

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

# ── RRF 融合 / 策略分发 ───────────────────
    if req.strategy == "parallel" and vector_ids:
        fused_ids = rrf_fusion(ft_ids, vector_ids)[:top_k * 2]

    elif req.strategy == "sequential":
        # 串行：先全文，不够再用向量补充
        fused_ids = list(ft_ids[:top_k])
        if len(fused_ids) < top_k:
            try:
                from ..services.embedder     import embed_query
                from ..services.milvus_store import search_sections
                query_vec   = embed_query(req.question)
                vec_results = search_sections(query_vec, top_k=top_k)
                seen = set(fused_ids)
                for r in vec_results:
                    if r["chunk_id"] not in seen and len(fused_ids) < top_k:
                        fused_ids.append(r["chunk_id"])
                        seen.add(r["chunk_id"])
                logger.info("串行检索补充至 %d 条", len(fused_ids))
            except Exception as e:
                logger.warning("串行向量补充失败: %s", e)

    elif req.strategy == "graph_augmented" and vector_ids:
        fused_ids = rrf_fusion(ft_ids, vector_ids)[:top_k * 2]

    else:
        fused_ids = ft_ids[:top_k * 2]

    # ── 图谱增强：从种子节点扩展邻居 ──────────
    if req.strategy == "graph_augmented" and fused_ids:
        try:
            with driver.session() as session:
                result = session.run("""
                    UNWIND $chunk_ids AS cid
                    MATCH (s:Section {chunk_id: cid})
                    OPTIONAL MATCH (s)-[:HAS_SUBSECTION|NEXT_SECTION]-(neighbor:Section)
                    OPTIONAL MATCH (parent:Section)-[:HAS_SUBSECTION]->(s)
                    WITH collect(DISTINCT s.chunk_id) +
                         collect(DISTINCT neighbor.chunk_id) +
                         collect(DISTINCT parent.chunk_id) AS all_ids
                    UNWIND all_ids AS id
                    WITH id WHERE id IS NOT NULL
                    RETURN collect(DISTINCT id) AS expanded_ids
                """, chunk_ids=fused_ids[:5])
                record       = result.single()
                expanded_ids = record["expanded_ids"] if record else []
                seen = set(fused_ids)
                for eid in expanded_ids:
                    if eid not in seen:
                        fused_ids.append(eid)
                        seen.add(eid)
                logger.info("图谱增强：扩展到 %d 个候选章节", len(fused_ids))
        except Exception as e:
            logger.warning("图谱增强失败: %s", e)

    # 最终截取 top_k
    fused_ids = fused_ids[:top_k * 2]

    # ── 获取章节详情 ──────────────────────────
    sections = get_section_details(driver, fused_ids)
    # ── Reranker 重排序 ───────────────────────────
    if sections and req.strategy in ("parallel", "graph_augmented"):
        try:
            from ..services.reranker import rerank
            sections = rerank(req.question, sections, top_k=top_k)
        except Exception as e:
            logger.warning("Reranker 失败，跳过重排序: %s", e)
    latency_ms = int((time.time() - start) * 1000)

    if not sections:
        answer = "在知识库中未找到相关章节，请确认文件已入库。"
    else:
        context = "\n\n".join(
            f"[{s['doc_id']} §{s['number']}] {s['title']}\n{s['content']}"
            for s in sections
        )
        try:
            from ..services.llm import generate_answer
            answer = generate_answer(
                question = req.question,
                context  = context,
            )
        except Exception as e:
            logger.warning("LLM 生成失败，降级返回检索结果: %s", e)
            answer = f"根据工艺规范知识库，检索到 {len(sections)} 个相关章节：\n\n{context[:2000]}"

    sources = [
        SourceSection(
            chunk_id = s["chunk_id"],
            doc_id   = s["doc_id"],
            number   = s["number"] or "",
            title    = s["title"]  or "",
            score    = round(s.get("rerank_score") or ft_score_map.get(s["chunk_id"], 0.0), 4),
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

    # ── 写入缓存 ──────────────────────────────
    set_cached_result(
        req.question, req.strategy, top_k,
        {"answer": answer, "sources": [s.model_dump() for s in sources]},
    )

    return QueryResponse(answer=answer, sources=sources)