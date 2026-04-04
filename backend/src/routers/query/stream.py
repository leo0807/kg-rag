"""
流式查询接口，支持多轮对话
"""
import json
import logging
from fastapi import Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from neo4j import Driver
from ...core.database import get_driver
from ...db.models import User
from .models import QueryRequest
from .core   import do_retrieval

logger = logging.getLogger(__name__)


async def query_stream(
    request:      Request,
    req:          QueryRequest,
    driver:       Driver = Depends(get_driver),
    current_user: User | None = None,
):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="question 不能为空")

    top_k = req.top_k or 5

    user_id    = current_user.id         if current_user else ""
    department = current_user.department if current_user else ""

    async def generate():
        from ...core.config import settings
        from ...core.observability import send_generation
        import httpx
        import time

        t_start = time.time()
        yield f"data: {json.dumps({'type': 'status', 'content': '检索中...'}, ensure_ascii=False)}\n\n"

        # 多跳推理单独处理，以便发送中间步骤
        if req.strategy == "multi_hop":
            try:
                from ...services.multi_hop import multi_hop_query
                answer_mh, mh_sections, mh_steps = multi_hop_query(req.question, driver, top_k=top_k)
                yield f"data: {json.dumps({'type': 'steps', 'content': mh_steps}, ensure_ascii=False)}\n\n"
                sources_mh = [
                    {
                        "chunk_id": s["chunk_id"], "doc_id": s["doc_id"],
                        "number":   s.get("number") or "", "title": s.get("title") or "",
                        "score":    round(float(s.get("score", 0)), 4),
                    }
                    for s in mh_sections
                ]
                yield f"data: {json.dumps({'type': 'sources', 'content': sources_mh}, ensure_ascii=False)}\n\n"
                for char in answer_mh:
                    yield f"data: {json.dumps({'type': 'delta', 'content': char}, ensure_ascii=False)}\n\n"
                latency_ms = int((time.time() - t_start) * 1000)
                send_generation(
                    name="graphrag-stream", model=settings.LLM_MODEL,
                    input_messages=[{"role": "user", "content": req.question}],
                    output=answer_mh, latency_ms=latency_ms, strategy="multi_hop",
                    user_id=user_id, department=department, question_preview=req.question,
                )
                yield "data: [DONE]\n\n"
                return
            except Exception as e:
                logger.warning("多跳流式推理失败，降级: %s", e)

        # ── 反事实图查询 ─────────────────────────────────────────────
        if req.strategy == "counterfactual":
            try:
                from ...services.counterfactual import prepare_counterfactual
                yield f"data: {json.dumps({'type': 'status', 'content': '分析因果链...'}, ensure_ascii=False)}\n\n"
                cf_sections, causal_chain, cf_messages = prepare_counterfactual(
                    req.question, driver, top_k=top_k
                )
                # 注入多轮对话历史（system + history + 当前用户消息）
                if req.history:
                    history_msgs = [
                        {"role": h.get("role", "user"), "content": h.get("content", "")}
                        for h in req.history[-10:]
                        if h.get("content", "").strip()
                    ]
                    # cf_messages = [system, user]; 在 system 和 user 之间插入历史
                    cf_messages = [cf_messages[0]] + history_msgs + [cf_messages[-1]]
                yield f"data: {json.dumps({'type': 'causal_chain', 'content': causal_chain}, ensure_ascii=False)}\n\n"
                sources_cf = [
                    {
                        "chunk_id": s["chunk_id"], "doc_id": s["doc_id"],
                        "number":   s.get("number") or "", "title": s.get("title") or "",
                        "score":    0.0,
                    }
                    for s in cf_sections
                ]
                yield f"data: {json.dumps({'type': 'sources', 'content': sources_cf}, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'type': 'status', 'content': '推理中...'}, ensure_ascii=False)}\n\n"

                full_answer   = ""
                prompt_tokens = 0
                compl_tokens  = 0
                try:
                    async with httpx.AsyncClient(timeout=90) as client:
                        async with client.stream(
                            "POST",
                            f"{settings.LLM_API_URL.rstrip('/')}/chat/completions",
                            headers={
                                "Authorization": f"Bearer {settings.LLM_API_KEY}",
                                "Content-Type":  "application/json",
                            },
                            json={
                                "model":          settings.LLM_MODEL,
                                "messages":       cf_messages,
                                "stream":         True,
                                "stream_options": {"include_usage": True},
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
                                    if chunk.get("usage") and not chunk.get("choices"):
                                        usage = chunk["usage"]
                                        prompt_tokens = usage.get("prompt_tokens", 0)
                                        compl_tokens  = usage.get("completion_tokens", 0)
                                        continue
                                    delta = chunk["choices"][0]["delta"].get("content", "")
                                    if delta:
                                        full_answer += delta
                                        yield f"data: {json.dumps({'type': 'delta', 'content': delta}, ensure_ascii=False)}\n\n"
                                except Exception:
                                    pass
                except Exception as e:
                    yield f"data: {json.dumps({'type': 'error', 'content': str(e)}, ensure_ascii=False)}\n\n"

                latency_ms = int((time.time() - t_start) * 1000)
                send_generation(
                    name="graphrag-stream", model=settings.LLM_MODEL,
                    input_messages=[{"role": "user", "content": req.question}],
                    output=full_answer, prompt_tokens=prompt_tokens, completion_tokens=compl_tokens,
                    latency_ms=latency_ms, strategy="counterfactual",
                    user_id=user_id, department=department, question_preview=req.question,
                )
                yield "data: [DONE]\n\n"
                return
            except Exception as e:
                logger.warning("反事实查询失败，降级到标准检索: %s", e)

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

        full_answer    = ""
        prompt_tokens  = 0
        compl_tokens   = 0
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
                        "model":          settings.LLM_MODEL,
                        "messages":       messages,
                        "stream":         True,
                        "stream_options": {"include_usage": True},
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
                            # 最终 usage chunk（choices 为空）
                            if chunk.get("usage") and not chunk.get("choices"):
                                usage = chunk["usage"]
                                prompt_tokens = usage.get("prompt_tokens", 0)
                                compl_tokens  = usage.get("completion_tokens", 0)
                                continue
                            delta = chunk["choices"][0]["delta"].get("content", "")
                            if delta:
                                full_answer += delta
                                yield f"data: {json.dumps({'type': 'delta', 'content': delta}, ensure_ascii=False)}\n\n"
                        except Exception:
                            pass
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)}, ensure_ascii=False)}\n\n"

        latency_ms = int((time.time() - t_start) * 1000)
        send_generation(
            name="graphrag-stream", model=settings.LLM_MODEL,
            input_messages=[{"role": "user", "content": req.question}],
            output=full_answer, prompt_tokens=prompt_tokens, completion_tokens=compl_tokens,
            latency_ms=latency_ms, strategy=req.strategy,
            user_id=user_id, department=department, question_preview=req.question,
        )
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )