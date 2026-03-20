import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ..services.retriever import retrieve, build_context
from ..services.llm import generate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["query"])


class QueryRequest(BaseModel):
    question: str
    # top_k 可以在请求时覆盖，不传则用 config 里的默认值
    top_k: int | None = None


class SourceSection(BaseModel):
    chunk_id:  str
    doc_id:    str
    number:    str
    title:     str
    score:     float   # 向量相似度分数，0~1，越高越相关


class QueryResponse(BaseModel):
    answer:  str
    sources: list[SourceSection]   # 告诉前端哪些章节被引用了，方便溯源


@router.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="question 不能为空")

    # 第一步：向量召回 + 图谱增强
    # retrieve() 返回的每条记录包含：命中章节、父章节、相邻章节
    records = retrieve(req.question)

    if not records:
        return QueryResponse(
            answer="在知识库中未找到相关章节，请确认文件已入库。",
            sources=[],
        )

    # 第二步：把图谱增强后的多段文本拼成一个 context 字符串
    context = build_context(records)

    # 第三步：把 context + 问题发给本地 LLM 生成答案
    answer = generate(req.question, context)

    # 第四步：整理来源列表，只暴露必要字段给前端
    sources = [
        SourceSection(
            chunk_id=r["chunk_id"],
            doc_id=r["doc_id"],
            number=r["number"],
            title=r["title"],
            score=round(r["score"], 4),
        )
        for r in records
    ]

    return QueryResponse(answer=answer, sources=sources)
