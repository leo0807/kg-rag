"""
流式查询接口，支持多轮对话
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Optional
from fastapi import Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from neo4j import Driver
from ...core.database import get_driver
from ...db.models import User
from ...services.llm_service import get_llm_service, LLMError
from .models import QueryRequest
from .core   import do_retrieval

logger = logging.getLogger(__name__)


def _error_event(e: Exception) -> str:
    """将异常序列化为 SSE error 事件字符串。"""
    if isinstance(e, LLMError):
        payload = {"type": "error", "code": e.code, "message": e.message,
                   "status_code": e.status_code, "endpoint": e.endpoint}
    else:
        payload = {"type": "error", "code": "unknown_error",
                   "message": "AI 服务异常，请联系管理员",
                   "status_code": None, "endpoint": ""}
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _format_section_ref(section: dict) -> str:
    """生成章节引用头，兼容 page_idx 为 None 的情况。"""
    doc_id = section.get("doc_id", "")
    number = section.get("number", "")
    title = section.get("title", "")
    page_idx = section.get("page_idx")
    page_text = f" (第{page_idx + 1}页)" if isinstance(page_idx, int) and page_idx >= 0 else ""
    return f"[{doc_id} §{number}{page_text}] {title}"


async def _emit_follow_ups(question: str, answer: str):
    """生成并 yield 追问建议 SSE 事件；失败静默跳过。"""
    import asyncio
    try:
        msgs = [
            {"role": "system", "content": "只输出一个 JSON 数组，格式：[\"问题1\",\"问题2\",\"问题3\"]，每条不超过30字，不要其他内容。"},
            {"role": "user",   "content": f"用户问题：{question}\n系统答案（节选）：{answer[:400]}\n\n请生成3条追问建议："},
        ]
        raw = await asyncio.wait_for(
            asyncio.to_thread(get_llm_service().chat, msgs), timeout=8.0
        )
        m = re.search(r'\[.*?\]', raw, re.DOTALL)
        if m:
            items = json.loads(m.group())
            questions = [str(q).strip() for q in items if str(q).strip()][:3]
            if questions:
                return json.dumps({"type": "follow_up", "content": questions}, ensure_ascii=False)
    except Exception as _e:
        logger.debug("追问建议生成失败（跳过）: %s", _e)
    return None


async def query_stream(
    request:      Request,
    req:          QueryRequest,
    driver:       Driver = Depends(get_driver),
    current_user: Optional[User] = None,
):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="question 不能为空")

    top_k = req.top_k or 5

    user_id    = current_user.id         if current_user else ""
    department = current_user.department if current_user else ""

    async def generate():
        from ...core.observability import send_generation
        import time

        t_start = time.time()
        try:
            _q_emb: list[float] | None = None
            try:
                from ...services.embedder import embed_texts
                from ...services import semantic_cache
                _q_emb = (await asyncio.to_thread(embed_texts, [req.question]) or [None])[0]
                hit = _q_emb and semantic_cache.lookup(_q_emb, req.strategy or "parallel")
                if hit:
                    sim = hit.get("similarity", 0)
                    yield f"data: {json.dumps({'type': 'status', 'content': f'⚡ 语义缓存命中（相似度 {sim:.3f}）'}, ensure_ascii=False)}\n\n"
                    yield f"data: {json.dumps({'type': 'sources', 'content': hit.get('sources', [])}, ensure_ascii=False)}\n\n"
                    cached_answer = hit.get("answer", "")
                    for char in cached_answer:
                        yield f"data: {json.dumps({'type': 'delta', 'content': char}, ensure_ascii=False)}\n\n"
                    yield "data: [DONE]\n\n"
                    try:
                        from ...db.session import AsyncSessionLocal
                        from ...db.models import CacheHit
                        tok = max(100, len(cached_answer) // 3)
                        async with AsyncSessionLocal() as db:
                            db.add(CacheHit(
                                user_id=user_id, department=department,
                                question_preview=req.question[:200],
                                matched_question_preview=hit.get("question_preview", "")[:200],
                                similarity=sim, strategy=req.strategy or "parallel",
                                cache_id=hit.get("cache_id", ""),
                                prompt_tokens_saved=tok, cost_saved_usd=round(tok * 0.000002, 6),
                            ))
                            await db.commit()
                    except Exception as _ce:
                        logger.warning("CacheHit 写入失败: %s", _ce)
                    return
            except Exception as _e:
                logger.debug("语义缓存查找异常（跳过）: %s", _e)

            yield f"data: {json.dumps({'type': 'status', 'content': '检索中...'}, ensure_ascii=False)}\n\n"

            # 多跳推理单独处理，以便发送中间步骤
            if req.strategy == "multi_hop":
                try:
                    from ...services.multi_hop import multi_hop_query_stream
                    full_answer = ""
                    async for event in multi_hop_query_stream(req.question, driver, top_k=top_k):
                        if event["type"] == "done":
                            break
                        if event["type"] == "delta":
                            full_answer += event["content"]
                        yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

                    latency_ms = int((time.time() - t_start) * 1000)
                    send_generation(
                        name="graphrag-stream", model=get_llm_service().model_name,
                        input_messages=[{"role": "user", "content": req.question}],
                        output=full_answer, latency_ms=latency_ms, strategy="multi_hop",
                        user_id=user_id, department=department, question_preview=req.question,
                    )
                    fu = await _emit_follow_ups(req.question, full_answer)
                    if fu:
                        yield f"data: {fu}\n\n"
                    yield "data: [DONE]\n\n"
                    return
                except Exception as e:
                    logger.warning("多跳流式推理失败，降级: %s", e)

            # 反事实图查询
            if req.strategy == "counterfactual":
                try:
                    from ...services.counterfactual import prepare_counterfactual
                    yield f"data: {json.dumps({'type': 'status', 'content': '分析因果链...'}, ensure_ascii=False)}\n\n"
                    cf_sections, causal_chain, cf_messages = prepare_counterfactual(
                        req.question, driver, top_k=top_k
                    )
                    if req.history:
                        history_msgs = [
                            {"role": h.get("role", "user"), "content": h.get("content", "")}
                            for h in req.history[-10:]
                            if h.get("content", "").strip()
                        ]
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

                    full_answer = ""
                    try:
                        async for delta in get_llm_service().stream_chat(cf_messages, timeout=90):
                            full_answer += delta
                            yield f"data: {json.dumps({'type': 'delta', 'content': delta}, ensure_ascii=False)}\n\n"
                    except Exception as e:
                        logger.exception("counterfactual stream_chat 失败")
                        yield _error_event(e)
                        yield "data: [DONE]\n\n"
                        return

                    latency_ms = int((time.time() - t_start) * 1000)
                    send_generation(
                        name="graphrag-stream", model=get_llm_service().model_name,
                        input_messages=[{"role": "user", "content": req.question}],
                        output=full_answer, latency_ms=latency_ms, strategy="counterfactual",
                        user_id=user_id, department=department, question_preview=req.question,
                    )
                    fu = await _emit_follow_ups(req.question, full_answer)
                    if fu:
                        yield f"data: {fu}\n\n"
                    yield "data: [DONE]\n\n"
                    return
                except Exception as e:
                    logger.exception("反事实查询失败，降级到标准检索")

            if req.use_hyde:
                yield f"data: {json.dumps({'type': 'status', 'content': '增强模式：生成假设答案...'}, ensure_ascii=False)}\n\n"
            sections, ft_score_map = do_retrieval(
                driver, req.question, req.strategy, top_k,
                use_hyde=req.use_hyde, hyde_alpha=req.hyde_alpha,
            )

            sources = [
                {
                    "chunk_id": s["chunk_id"], "doc_id": s["doc_id"],
                    "number":   s.get("number") or "", "title": s.get("title") or "",
                    "score":    round(s.get("rerank_score") or ft_score_map.get(s["chunk_id"], 0.0), 4),
                    "page_idx": s.get("page_idx"),
                    "bbox":     s.get("bbox"),
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
                f"{_format_section_ref(s)}\n{s['content']}"
                for s in sections
            )

            # 构建多轮对话
            messages = [
                {
                    "role":    "system",
                    "content": "你是一个航空制造工艺规范专家助手。请根据提供的规范内容，用中文准确回答问题。如果问题与之前的对话相关，请结合上下文回答。",
                }
            ]

            for h in req.history[-12:]:
                messages.append({"role": h.get("role", "user"), "content": h.get("content", "")})

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

            full_answer = ""
            try:
                async for delta in get_llm_service().stream_chat(messages, timeout=60):
                    full_answer += delta
                    yield f"data: {json.dumps({'type': 'delta', 'content': delta}, ensure_ascii=False)}\n\n"
            except Exception as e:
                logger.exception("query stream_chat 失败")
                yield _error_event(e)
                yield "data: [DONE]\n\n"
                return

            latency_ms = int((time.time() - t_start) * 1000)
            send_generation(
                name="graphrag-stream", model=get_llm_service().model_name,
                input_messages=[{"role": "user", "content": req.question}],
                output=full_answer, latency_ms=latency_ms, strategy=req.strategy,
                user_id=user_id, department=department, question_preview=req.question,
            )
            # 写入语义缓存
            if _q_emb and full_answer.strip():
                try:
                    from ...services import semantic_cache
                    doc_ids = list({s["doc_id"] for s in sources if s.get("doc_id")})
                    await asyncio.to_thread(
                        semantic_cache.store,
                        _q_emb, req.strategy or "parallel", full_answer,
                        sources, req.question[:200], doc_ids,
                    )
                except Exception as _se:
                    logger.debug("语义缓存写入失败（跳过）: %s", _se)
            fu = await _emit_follow_ups(req.question, full_answer)
            if fu:
                yield f"data: {fu}\n\n"
            yield "data: [DONE]\n\n"
        except asyncio.CancelledError:
            logger.info("query_stream cancelled by client")
            raise
        except Exception as e:
            logger.exception("query_stream 未捕获异常: %s", e)
            if await request.is_disconnected():
                return
            yield _error_event(e)
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
