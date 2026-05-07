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
from sqlalchemy.ext.asyncio import AsyncSession
from ...core.database import get_driver
from ...db.models import User
from ...services.ai.llm import clean_llm_response
from ...services.ai.llm_service import get_llm_service
from ...services.runtime.model_settings import load_effective_settings, use_runtime_settings
from .models import QueryRequest
from .core   import do_retrieval
from .clarification_utils import build_clarification_event, detect_clarification
from .context_utils import build_llm_context, reorder_sources_for_llm
from .stream_agent import stream_agent_query
from .stream_utils import _error_event, _emit_follow_ups
logger = logging.getLogger(__name__)
async def query_stream(
    request:      Request,
    req:          QueryRequest,
    driver:       Driver = Depends(get_driver),
    current_user: Optional[User] = None,
    db:           AsyncSession | None = None,
):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="question 不能为空")
    top_k = req.top_k or 5
    effective_settings = await load_effective_settings(db, current_user.id if current_user else None)
    user_id    = current_user.id         if current_user else ""
    department = current_user.department if current_user else ""
    async def generate():
        from ...core.observability import send_generation
        import time
        with use_runtime_settings(effective_settings):
            t_start = time.time()
            try:
                clarification = await detect_clarification(req.question, driver)
                if clarification.get("needs_clarification"):
                    yield build_clarification_event(req.question, clarification)
                    yield "data: [DONE]\n\n"
                    return
                _q_emb: list[float] | None = None
                try:
                    from ...services.retrieval.embedder import embed_texts
                    from ...services.retrieval import semantic_cache
                    _q_emb = (await asyncio.to_thread(embed_texts, [req.question]) or [None])[0]
                    hit = _q_emb and semantic_cache.lookup(_q_emb, req.strategy or "parallel")
                    if hit:
                        sim = hit.get("similarity", 0)
                        yield f"data: {json.dumps({'type': 'status', 'content': f'⚡ 语义缓存命中（相似度 {sim:.3f}）'}, ensure_ascii=False)}\n\n"
                        yield f"data: {json.dumps({'type': 'sources', 'content': hit.get('sources', [])}, ensure_ascii=False)}\n\n"
                        cached_answer = clean_llm_response(hit.get("answer", ""))
                        for char in cached_answer:
                            yield f"data: {json.dumps({'type': 'delta', 'content': char}, ensure_ascii=False)}\n\n"
                        yield "data: [DONE]\n\n"
                        try:
                            from ...db.session import AsyncSessionLocal
                            from ...db.models import CacheHit
                            tok = max(100, len(cached_answer) // 3)
                            async with AsyncSessionLocal() as db_session:
                                db_session.add(CacheHit(
                                    user_id=user_id, department=department,
                                    question_preview=req.question[:200],
                                    matched_question_preview=hit.get("question_preview", "")[:200],
                                    similarity=sim, strategy=req.strategy or "parallel",
                                    cache_id=hit.get("cache_id", ""),
                                    prompt_tokens_saved=tok, cost_saved_usd=round(tok * 0.000002, 6),
                                ))
                                await db_session.commit()
                        except Exception as _ce:
                            logger.warning("CacheHit 写入失败: %s", _ce)
                        return
                except Exception as _e:
                    logger.debug("语义缓存查找异常（跳过）: %s", _e)

                yield f"data: {json.dumps({'type': 'status', 'content': '检索中...'}, ensure_ascii=False)}\n\n"
                if req.strategy == "multi_hop":
                    try:
                        from ...services.retrieval.multi_hop import multi_hop_query_stream
                        full_answer = ""
                        async for event in multi_hop_query_stream(req.question, driver, top_k=top_k):
                            if event["type"] == "done":
                                break
                            if event["type"] == "delta":
                                delta = clean_llm_response(event["content"])
                                full_answer += delta
                                event = {**event, "content": delta}
                            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                        latency_ms = int((time.time() - t_start) * 1000)
                        full_answer = clean_llm_response(full_answer)
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
                if req.strategy == "agent":
                    try:
                        async for event in stream_agent_query(
                            req.question, driver, top_k, t_start, user_id, department
                        ):
                            yield event
                        return
                    except Exception:
                        logger.exception("Agent 流式推理失败，降级到标准检索")
                if req.strategy == "counterfactual":
                    try:
                        from ...services.retrieval.counterfactual import prepare_counterfactual
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
                                "score":    round(float(s.get("score") or s.get("rrf_score") or 0.0), 4),
                            }
                            for s in cf_sections
                        ]
                        yield f"data: {json.dumps({'type': 'sources', 'content': sources_cf}, ensure_ascii=False)}\n\n"
                        yield f"data: {json.dumps({'type': 'status', 'content': '推理中...'}, ensure_ascii=False)}\n\n"

                        full_answer = ""
                        try:
                            async for delta in get_llm_service().stream_chat(cf_messages, timeout=90):
                                delta = clean_llm_response(delta)
                                full_answer += delta
                                yield f"data: {json.dumps({'type': 'delta', 'content': delta}, ensure_ascii=False)}\n\n"
                        except Exception as e:
                            logger.exception("counterfactual stream_chat 失败")
                            yield _error_event(e)
                            yield "data: [DONE]\n\n"
                            return

                        latency_ms = int((time.time() - t_start) * 1000)
                        full_answer = clean_llm_response(full_answer)
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
                _t_retrieval = time.time()
                sections, ft_score_map, expansion_info = await asyncio.to_thread(
                    do_retrieval,
                    driver, req.question, req.strategy, top_k,
                    req.use_hyde, req.hyde_alpha,
                )
                _retrieval_ms = int((time.time() - _t_retrieval) * 1000)
                if expansion_info:
                    yield f"data: {json.dumps({'type': 'expansion', 'content': expansion_info}, ensure_ascii=False)}\n\n"

                sources = [
                    {
                        "chunk_id": s["chunk_id"], "doc_id": s["doc_id"],
                        "number":   s.get("number") or "", "title": s.get("title") or "",
                        "score":    round(
                            s.get("score")
                            or
                            s.get("rrf_score")
                            or s.get("rerank_score")
                            or ft_score_map.get(s["chunk_id"], 0.0),
                            4,
                        ),
                        "page_idx": s.get("page_idx"),
                        "bbox":     s.get("bbox"),
                        "source_type": s.get("source_type", []),
                        "retrieval_trace": s.get("retrieval_trace", []),
                        "is_graph_expanded": bool(s.get("is_graph_expanded")),
                        "is_vector_hit": bool(s.get("is_vector_hit")),
                        "is_fulltext_hit": bool(s.get("is_fulltext_hit")),
                        "is_gnn_hit": bool(s.get("is_gnn_hit")),
                    }
                    for s in sections
                ]
                yield f"data: {json.dumps({'type': 'sources', 'content': sources}, ensure_ascii=False)}\n\n"
                if not sections:
                    yield f"data: {json.dumps({'type': 'delta', 'content': '在知识库中未找到相关章节。'}, ensure_ascii=False)}\n\n"
                    yield "data: [DONE]\n\n"
                    return

                yield f"data: {json.dumps({'type': 'status', 'content': '生成回答中...'}, ensure_ascii=False)}\n\n"
                llm_sections = reorder_sources_for_llm(sections, req.question)
                context = build_llm_context(llm_sections)

                messages = [
                    {
                        "role":    "system",
                        "content": "你是一个航空制造工艺规范专家助手。请根据提供的规范内容，用中文准确回答问题。回答时优先使用来源中的直接定义和描述，不要过多展开次要细节。如果问题询问'特性'或'性质'，优先引用定义类章节（术语定义、基本要求章节），而不是参数表格。如果来源中出现 'soft and ductile paste'、'solid and elastic rubber' 之类表述，可直接概括为'粘性和弹性'。如果问题与之前的对话相关，请结合上下文回答。",
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
                _t_llm = time.time()
                try:
                    async for delta in get_llm_service().stream_chat(messages, timeout=60):
                        delta = clean_llm_response(delta)
                        full_answer += delta
                        yield f"data: {json.dumps({'type': 'delta', 'content': delta}, ensure_ascii=False)}\n\n"
                except Exception as e:
                    logger.exception("query stream_chat 失败")
                    yield _error_event(e)
                    yield "data: [DONE]\n\n"
                    return

                _llm_ms    = int((time.time() - _t_llm) * 1000)
                latency_ms = int((time.time() - t_start) * 1000)
                full_answer = clean_llm_response(full_answer)
                send_generation(
                    name="graphrag-stream", model=get_llm_service().model_name,
                    input_messages=[{"role": "user", "content": req.question}],
                    output=full_answer, latency_ms=latency_ms, strategy=req.strategy,
                    user_id=user_id, department=department, question_preview=req.question,
                )
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
                _metrics = {
                    "total_ms": latency_ms,
                    "stages": {"检索": _retrieval_ms, "LLM生成": _llm_ms},
                    "tokens": {}, "cost_usd": 0.0,
                    "candidates_retrieved": len(sections),
                    "candidates_after_rerank": len(sources),
                }
                yield f"data: {json.dumps({'type': 'metrics', 'content': _metrics}, ensure_ascii=False)}\n\n"
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
