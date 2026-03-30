"""
流式查询接口，支持多轮对话
"""
import json
import logging
from fastapi import Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from neo4j import Driver
from ...core.database import get_driver
from .models import QueryRequest
from .core   import do_retrieval

logger = logging.getLogger(__name__)


async def query_stream(
    request: Request,
    req:     QueryRequest,
    driver:  Driver = Depends(get_driver),
):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="question 不能为空")

    top_k = req.top_k or 5

    async def generate():
        from ...core.config import settings
        import httpx

        yield f"data: {json.dumps({'type': 'status', 'content': '检索中...'}, ensure_ascii=False)}\n\n"

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

        # ── 构建多轮对话 ──────────────────────────
        messages = [
            {
                "role":    "system",
                "content": "你是一个航空制造工艺规范专家助手。请根据提供的规范内容，用中文准确回答问题。如果问题与之前的对话相关，请结合上下文回答。",
            }
        ]

        # 加入历史对话（最近6轮=12条）
        for h in req.history[-12:]:
            messages.append({
                "role":    h.get("role", "user"),
                "content": h.get("content", ""),
            })

        # 当前问题附带检索上下文（支持多模态图片）
        user_text = f"## 相关规范内容\n\n{context}\n\n## 问题\n\n{req.question}"
        if req.images:
            user_content: list = [{"type": "text", "text": user_text}]
            for img_uri in req.images:
                user_content.append({
                    "type": "image_url",
                    "image_url": {"url": img_uri},
                })
            messages.append({"role": "user", "content": user_content})
        else:
            messages.append({"role": "user", "content": user_text})

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
                        "messages": messages,
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