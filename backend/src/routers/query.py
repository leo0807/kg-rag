import logging
import time
from fastapi import APIRouter, Depends, HTTPException
from neo4j import Driver
from pydantic import BaseModel
from ..core.database import get_driver
from ..core.observability import send_trace
from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["query"])


class QueryRequest(BaseModel):
    question: str
    top_k:    int | None = None


class SourceSection(BaseModel):
    chunk_id: str
    doc_id:   str
    number:   str
    title:    str
    score:    float


class QueryResponse(BaseModel):
    answer:  str
    sources: list[SourceSection]

@router.post("/query", response_model=QueryResponse)
@limiter.limit("30/minute")
# 限流后函数签名必须包含 request: Request 参数，slowapi 需要它来获取客户端 IP
async def query(request: Request, req: QueryRequest, driver: Driver = Depends(get_driver)):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="question 不能为空")

    top_k = req.top_k or 5
    start = time.time()

    with driver.session() as session:
        result = session.run("""
            CALL db.index.fulltext.queryNodes(
                'cps_fulltext_index', $question
            ) YIELD node, score
            RETURN node.chunk_id        AS chunk_id,
                   node.doc_id          AS doc_id,
                   node.section_number  AS number,
                   node.title           AS title,
                   node.content         AS content,
                   score
            ORDER BY score DESC
            LIMIT $top_k
        """, question=req.question, top_k=top_k)
        records = [dict(r) for r in result]

    latency_ms = int((time.time() - start) * 1000)

    if not records:
        answer = "在知识库中未找到相关章节，请确认文件已入库。"
    else:
        context = "\n\n".join(
            f"[{r['doc_id']} §{r['number']}] {r['title']}\n{r['content']}"
            for r in records[:3]
        )
        answer = f"根据工艺规范知识库，检索到 {len(records)} 个相关章节：\n\n{context[:1000]}"

    sources = [
        SourceSection(
            chunk_id=r["chunk_id"],
            doc_id=r["doc_id"],
            number=r["number"] or "",
            title=r["title"] or "",
            score=round(float(r["score"]), 4),
        )
        for r in records
    ]

    # Langfuse 追踪
    send_trace(
        name="graphrag-query",
        input=req.question,
        output=answer,
        metadata={
            "strategy":     "graph_fulltext",
            "latency_ms":   latency_ms,
            "chunks_found": len(records),
            "sources":      [s.chunk_id for s in sources],
        },
    )

    return QueryResponse(answer=answer, sources=sources)