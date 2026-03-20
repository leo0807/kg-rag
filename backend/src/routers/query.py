import json
import logging
from collections.abc import Generator
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from ..services.retriever import retrieve, build_context
from ..services.llm import generate, generate_stream

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


@router.post("/query/stream")
async def query_stream(req: QueryRequest):
    """
    流式版本的 /api/query，使用 Server-Sent Events（SSE）协议。

    SSE 是 HTTP 长连接上的单向推流，浏览器原生支持 EventSource API，
    不需要 WebSocket，适合"问题→逐字生成答案"这种单向场景。

    每帧格式：data: <JSON>\n\n
    帧类型（JSON 中的 type 字段）：
      - token  ：LLM 输出的一个文本片段，前端直接追加到显示区域
      - sources：所有引用章节，在 LLM 生成完毕后发送
      - done   ：结束信号，前端收到后关闭连接
    """
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="question 不能为空")

    records = retrieve(req.question)

    if not records:
        # 没有召回结果时直接结束，不调用 LLM
        async def empty():
            yield _sse({"type": "token", "content": "在知识库中未找到相关章节，请确认文件已入库。"})
            yield _sse({"type": "done"})
        return StreamingResponse(empty(), media_type="text/event-stream")

    context = build_context(records)
    sources = [
        SourceSection(
            chunk_id=r["chunk_id"],
            doc_id=r["doc_id"],
            number=r["number"],
            title=r["title"],
            score=round(r["score"], 4),
        ).model_dump()
        for r in records
    ]

    def event_generator() -> Generator[str, None, None]:
        # generate_stream 是同步生成器，在这里直接迭代
        for token in generate_stream(req.question, context):
            yield _sse({"type": "token", "content": token})
        # LLM 生成完毕后，发送来源列表和结束信号
        yield _sse({"type": "sources", "sources": sources})
        yield _sse({"type": "done"})

    return StreamingResponse(event_generator(), media_type="text/event-stream")


def _sse(data: dict) -> str:
    """把字典序列化成标准 SSE 帧格式：data: <json>\n\n"""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
