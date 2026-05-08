"""
流式查询接口，支持多轮对话
"""
from __future__ import annotations
import asyncio
import json
import logging
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
from .stream_utils import (
    _error_event,
    _emit_follow_ups,
    emit_status_event,
    estimate_answer_max_tokens,
    serialize_sources,
    stream_semantic_cache_hit,
    try_semantic_cache_lookup,
    stream_with_first_token_logging,
)
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
                logger.info("[timing] 开始检索 t=%.2fs", time.time() - t_start)
                yield emit_status_event("正在检索相关规范...")
                clarification = await detect_clarification(
                    req.question,
                    driver,
                    skip=req.skip_clarification,
                )
                if clarification.get("needs_clarification"):
                    yield build_clarification_event(req.question, clarification)
                    yield "data: [DONE]\n\n"
                    return
                _q_emb: list[float] | None = None
                try:
                    timeout_s = float(getattr(effective_settings, "SEMANTIC_CACHE_LOOKUP_TIMEOUT", 1.0) or 1.0)
                    _q_emb, hit = await try_semantic_cache_lookup(req.question, req.strategy or "parallel", timeout_s)
                    if hit:
                        async for event in stream_semantic_cache_hit(
                            hit, req.question, user_id, department, req.strategy or "parallel"
                        ):
                            yield event
                        return
                except Exception as _e:
                    logger.debug("语义缓存查找异常（跳过）: %s", _e)
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
                    yield emit_status_event("增强模式：生成假设答案...")
                _t_retrieval = time.time()
                sections, ft_score_map, expansion_info = await asyncio.to_thread(
                    do_retrieval,
                    driver, req.question, req.strategy, top_k,
                    req.use_hyde, req.hyde_alpha, "", True,
                )
                _retrieval_ms = int((time.time() - t_start) * 1000)
                logger.info("[timing] 检索完成 t=%.2fs", time.time() - t_start)
                if expansion_info:
                    yield f"data: {json.dumps({'type': 'expansion', 'content': expansion_info}, ensure_ascii=False)}\n\n"
                sources = serialize_sources(sections, ft_score_map)
                yield f"data: {json.dumps({'type': 'sources', 'content': sources}, ensure_ascii=False)}\n\n"
                if not sections:
                    yield f"data: {json.dumps({'type': 'delta', 'content': '在知识库中未找到相关章节。'}, ensure_ascii=False)}\n\n"
                    yield "data: [DONE]\n\n"
                    return
                yield emit_status_event("正在生成答案...")
                rerank_task = None
                rerank_sent = False
                if req.strategy in ("parallel", "graph_augmented", "sequential", "gnn", "hybrid_es") and sections:
                    try:
                        from ...services.retrieval.reranker import rerank
                        rerank_task = asyncio.create_task(asyncio.to_thread(rerank, req.question, sections, top_k))
                    except Exception as _re:
                        logger.debug("后台 rerank 任务启动失败（跳过）: %s", _re)
                llm_sections = reorder_sources_for_llm(sections, req.question)
                context = build_llm_context(llm_sections)
                answer_max_tokens = estimate_answer_max_tokens(req.question, context)
                messages = [
                    {
                        "role":    "system",
                        "content": "你是一个航空制造工艺规范专家助手。请根据提供的规范内容，用中文准确回答问题。回答时优先使用来源中的直接定义和描述，不要过多展开次要细节。如果问题询问'特性'或'性质'，优先引用定义类章节（术语定义、基本要求章节），而不是参数表格。如果来源中出现 'soft and ductile paste'、'solid and elastic rubber' 之类表述，可直接概括为'粘性和弹性'。如果问题与之前的对话相关，请结合上下文回答。",
                    }
                ]
                for h in req.history[-12:]: messages.append({"role": h.get("role", "user"), "content": h.get("content", "")})
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
                    async for delta in stream_with_first_token_logging(
                        get_llm_service(),
                        messages,
                        timeout=answer_max_tokens,
                        t_start=t_start,
                        logger=logger,
                    ):
                        if rerank_task is not None and not rerank_sent and rerank_task.done():
                            try:
                                reranked_sections = rerank_task.result()
                                if reranked_sections:
                                    sources = serialize_sources(reranked_sections, ft_score_map)
                                    yield f"data: {json.dumps({'type': 'sources_update', 'content': sources}, ensure_ascii=False)}\n\n"
                            except Exception as _re:
                                logger.debug("后台 rerank 失败（跳过）: %s", _re)
                            rerank_sent = True
                        delta = clean_llm_response(delta)
                        full_answer += delta
                        yield f"data: {json.dumps({'type': 'delta', 'content': delta}, ensure_ascii=False)}\n\n"
                except Exception as e:
                    logger.exception("query stream_chat 失败")
                    yield _error_event(e)
                    yield "data: [DONE]\n\n"
                    return
                if rerank_task is not None and not rerank_sent:
                    try:
                        reranked_sections = await rerank_task
                        if reranked_sections:
                            sources = serialize_sources(reranked_sections, ft_score_map)
                            yield f"data: {json.dumps({'type': 'sources_update', 'content': sources}, ensure_ascii=False)}\n\n"
                    except Exception as _re:
                        logger.debug("后台 rerank 失败（跳过）: %s", _re)
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
                _llm_ms = max(0, latency_ms - _retrieval_ms); _metrics = {
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
    return StreamingResponse(generate(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
