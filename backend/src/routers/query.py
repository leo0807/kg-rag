import logging
import time
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
import json
from neo4j import Driver
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address
from ..core.database import get_driver
from ..core.observability import send_trace
from ..services.cache import get_cached_result, set_cached_result

logger  = logging.getLogger(__name__)
router  = APIRouter(prefix="/api", tags=["query"])
limiter = Limiter(key_func=get_remote_address)


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


def rrf_fusion(fulltext_ids: list[str], vector_ids: list[str], k: int = 60) -> list[str]:
    scores: dict[str, float] = {}
    for rank, chunk_id in enumerate(fulltext_ids, start=1):
        scores[chunk_id] = scores.get(chunk_id, 0) + 1 / (k + rank)
    for rank, chunk_id in enumerate(vector_ids, start=1):
        scores[chunk_id] = scores.get(chunk_id, 0) + 1 / (k + rank)
    return sorted(scores, key=lambda x: scores[x], reverse=True)


def get_section_details(driver: Driver, chunk_ids: list[str]) -> list[dict]:
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
    return [records[cid] for cid in chunk_ids if cid in records]


def do_retrieval(driver: Driver, question: str, strategy: str, top_k: int):
    """执行检索，返回 (sections, ft_score_map)"""

    # ── ES 全文检索（替代 Neo4j 全文索引）────
    ft_ids       = []
    ft_score_map = {}
    try:
        from ..services.es_store import search_sections_es
        es_results   = search_sections_es(question, top_k=top_k * 2)
        ft_ids       = [r["chunk_id"] for r in es_results]
        ft_score_map = {r["chunk_id"]: r["score"] for r in es_results}
        logger.info("ES 检索到 %d 个候选", len(ft_ids))
    except Exception as e:
        logger.warning("ES 检索失败，降级到 Neo4j: %s", e)
        with driver.session() as session:
            ft_result = session.run("""
                CALL db.index.fulltext.queryNodes('cps_fulltext_index', $question)
                YIELD node, score
                RETURN node.chunk_id AS chunk_id, score
                ORDER BY score DESC LIMIT $top_k
            """, question=question, top_k=top_k * 2)
            ft_records   = [dict(r) for r in ft_result]
            ft_ids       = [r["chunk_id"] for r in ft_records]
            ft_score_map = {r["chunk_id"]: r["score"] for r in ft_records}

    # ── 向量检索 ──────────────────────────────
    vector_ids = []
    if strategy in ("parallel", "graph_augmented"):
        try:
            from ..services.embedder     import embed_query
            from ..services.milvus_store import search_sections
            vec_results = search_sections(embed_query(question), top_k=top_k * 2)
            vector_ids  = [r["chunk_id"] for r in vec_results]
        except Exception as e:
            logger.warning("向量检索失败: %s", e)

    # ── 策略分发 ──────────────────────────────
    if strategy == "parallel" and vector_ids:
        fused_ids = rrf_fusion(ft_ids, vector_ids)[:top_k * 2]

    elif strategy == "sequential":
        fused_ids = list(ft_ids[:top_k])
        if len(fused_ids) < top_k:
            try:
                from ..services.embedder     import embed_query
                from ..services.milvus_store import search_sections
                vec_results = search_sections(embed_query(question), top_k=top_k)
                seen = set(fused_ids)
                for r in vec_results:
                    if r["chunk_id"] not in seen and len(fused_ids) < top_k:
                        fused_ids.append(r["chunk_id"])
                        seen.add(r["chunk_id"])
                logger.info("串行检索补充至 %d 条", len(fused_ids))
            except Exception as e:
                logger.warning("串行向量补充失败: %s", e)

    elif strategy == "graph_augmented" and vector_ids:
        fused_ids = rrf_fusion(ft_ids, vector_ids)[:top_k * 2]

    else:
        fused_ids = ft_ids[:top_k * 2]

    # ── 图谱增强扩展 ──────────────────────────
    if strategy == "graph_augmented" and fused_ids:
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

    fused_ids = fused_ids[:top_k * 2]
    sections  = get_section_details(driver, fused_ids)

    # ── Reranker ──────────────────────────────
    if sections and strategy in ("parallel", "graph_augmented"):
        try:
            from ..services.reranker import rerank
            sections = rerank(question, sections, top_k=top_k)
        except Exception as e:
            logger.warning("Reranker 失败: %s", e)

    return sections, ft_score_map

@router.post("/query", response_model=QueryResponse)
@limiter.limit("30/minute")
async def query(request: Request, req: QueryRequest, driver: Driver = Depends(get_driver)):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="question 不能为空")

    top_k  = req.top_k or 5
    cached = get_cached_result(req.question, req.strategy, top_k)
    if cached:
        return QueryResponse(**cached)

    start = time.time()

    # 多跳推理
    if req.strategy == "multi_hop":
        try:
            from ..services.multi_hop import multi_hop_query
            answer, multi_hop_sections = multi_hop_query(req.question, driver, top_k=top_k)
            sources = [
                SourceSection(
                    chunk_id=s["chunk_id"], doc_id=s["doc_id"],
                    number=s.get("number") or "", title=s.get("title") or "",
                    score=round(float(s.get("score", 0)), 4),
                )
                for s in multi_hop_sections
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
            from ..services.llm import generate_answer
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
               metadata={"strategy": req.strategy, "latency_ms": latency_ms,
                         "ft_count": len(ft_score_map), "fused_count": len(sections)})
    set_cached_result(req.question, req.strategy, top_k,
                      {"answer": answer, "sources": [s.model_dump() for s in sources]})
    return QueryResponse(answer=answer, sources=sources)


@router.post("/query/stream")
@limiter.limit("30/minute")
async def query_stream(request: Request, req: QueryRequest, driver: Driver = Depends(get_driver)):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="question 不能为空")

    top_k = req.top_k or 5

    async def generate():
        from ..core.config import settings
        import httpx

        yield f"data: {json.dumps({'type': 'status', 'content': '检索中...'}, ensure_ascii=False)}\n\n"

        # 检索
        sections, ft_score_map = do_retrieval(driver, req.question, req.strategy, top_k)

        sources = [
            {
                "chunk_id": s["chunk_id"], "doc_id": s["doc_id"],
                "number":   s.get("number") or "", "title": s.get("title") or "",
                "score":    round(s.get("rerank_score") or ft_score_map.get(s["chunk_id"], 0.0), 4),
            }
            for s in sections
        ]
        yield f"data: {json.dumps({'type': 'sources', 'content': sources}, ensure_ascii=False)}\n\n"

        if not sections:
            yield f"data: {json.dumps({'type': 'delta', 'content': '在知识库中未找到相关章节。'}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            return

        yield f"data: {json.dumps({'type': 'status', 'content': '生成回答中...'}, ensure_ascii=False)}\n\n"

        context = "\n\n".join(
            f"[{s['doc_id']} §{s['number']}] {s['title']}\n{s['content']}"
            for s in sections
        )
        prompt = f"""你是一个航空制造工艺规范专家助手。请根据以下工艺规范文档内容，用中文回答用户的问题。

## 相关工艺规范内容

{context}

## 用户问题

{req.question}

请回答："""

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                async with client.stream(
                    "POST",
                    f"{settings.LLM_API_URL.rstrip('/')}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {settings.LLM_API_KEY}",
                        "Content-Type":  "application/json",
                    },
                    json={
                        "model":    settings.LLM_MODEL,
                        "messages": [{"role": "user", "content": prompt}],
                        "stream":   True,
                    },
                ) as response:
                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            delta = chunk["choices"][0]["delta"].get("content", "")
                            if delta:
                                yield f"data: {json.dumps({'type': 'delta', 'content': delta}, ensure_ascii=False)}\n\n"
                        except Exception:
                            pass
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)}, ensure_ascii=False)}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )