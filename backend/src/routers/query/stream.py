"""
流式查询接口，支持多轮对话
"""
from __future__ import annotations
import asyncio, json, logging, time
from typing import Optional
from fastapi import Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from neo4j import Driver
from sqlalchemy.ext.asyncio import AsyncSession
from ...core.database import get_driver
from ...core.config import settings as app_settings
from ...db.models import User
from ...services.ai.llm import clean_llm_response
from ...services.ai.llm_service import get_llm_service
from ...services.context_utils import resolve_retrieval_doc_id, trim_conversation_history_for_question
from ...services.query_count import maybe_build_total_cps_count_events
from ...services.runtime.model_settings import load_effective_settings, use_runtime_settings
from ...core.shutdown import shutdown_tracker
from .query_utils import finalize_answer_text, log_source_doc_ids, emit_generation_record
from .models import QueryRequest
from .core   import do_retrieval
from .clarification_utils import build_clarification_event, detect_clarification
from .context_utils import build_llm_context, reorder_sources_for_llm
from .stream_compare import build_compare_stream_events
from .stream_agent import stream_agent_query
from .stream_multimodal import stream_multimodal_query
from .mcq_utils import maybe_answer_mcq_stream, forward_mcq_stream
from ...services.qa.strategy_router import select_strategy
from .stream_utils import _error_event, _emit_follow_ups, build_metrics_event, clean_stream_chunk, emit_status_event, estimate_answer_max_tokens, get_question_handler_for, serialize_sources, stream_semantic_cache_hit, try_semantic_cache_lookup, stream_with_first_token_logging
logger = logging.getLogger(__name__)
async def query_stream(request: Request, req: QueryRequest, driver: Driver = Depends(get_driver), current_user: Optional[User] = None, db: AsyncSession | None = None):
    if not req.question.strip(): raise HTTPException(status_code=400, detail="question 不能为空")
    top_k = req.top_k or 5; cache_question = req.question if not req.image_context else f"{req.question}\n\n{req.image_context[:500]}"
    effective_settings = await load_effective_settings(db, current_user.id if current_user else None)
    user_id = current_user.id if current_user else ""; department = current_user.department if current_user else ""
    async def generate():
        with use_runtime_settings(effective_settings):
            t_start = time.time()
            async with shutdown_tracker.track_stream():
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
                    if count_events := await maybe_build_total_cps_count_events(req.question, req.strategy, top_k, driver, user_id, department):
                        for event in count_events:
                            yield event
                        return
                    _q_emb: list[float] | None = None
                    try:
                        timeout_s = float(getattr(effective_settings, "SEMANTIC_CACHE_LOOKUP_TIMEOUT", 1.0) or 1.0)
                        _q_emb, hit = await try_semantic_cache_lookup(cache_question, req.strategy or "parallel", timeout_s)
                        if hit:
                            async for event in stream_semantic_cache_hit(
                                hit, cache_question, user_id, department, req.strategy or "parallel"
                            ):
                                yield event
                            return
                    except Exception as _e:
                        logger.debug("语义缓存查找异常（跳过）: %s", _e)
                    mcq_events = maybe_answer_mcq_stream(req.question, req.strategy, top_k, driver, user_id, department, t_start, req.doc_hints, _q_emb)
                    try:
                        first_mcq_event = await anext(mcq_events)
                    except StopAsyncIteration:
                        pass  # 非选择题，继续标准检索流程
                    else:
                        yield first_mcq_event
                        async for event in forward_mcq_stream(mcq_events):
                            yield event
                        return
                    if req.strategy == "auto":
                        req.strategy, _ = select_strategy(req.question)
                    if req.strategy == "multi_hop":
                        try:
                            from ...services.retrieval.multi_hop import multi_hop_query_stream
                            full_answer = ""
                            mh_sources: list[dict] = []
                            async for event in multi_hop_query_stream(req.question, driver, top_k=top_k):
                                if event["type"] == "done":
                                    break
                                if event["type"] == "sources":
                                    mh_sources = event.get("content") or mh_sources
                                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                                    continue
                                if event["type"] == "delta":
                                    delta = clean_llm_response(event["content"])
                                    full_answer += delta
                                    event = {**event, "content": delta}
                                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                            latency_ms = int((time.time() - t_start) * 1000)
                            full_answer = finalize_answer_text(full_answer, mh_sources, req.question)
                            emit_generation_record(strategy="multi_hop", question=req.question, answer=full_answer, latency_ms=latency_ms, user_id=user_id, department=department, model_name=get_llm_service().model_name)
                            fu = await _emit_follow_ups(req.question, full_answer, [s.get("doc_id") for s in mh_sources if s.get("doc_id")])
                            if fu:
                                yield f"data: {fu}\n\n"
                            yield "data: [DONE]\n\n"
                            return
                        except Exception as e:
                            logger.warning("多跳流式推理失败，降级: %s", e)
                    if req.strategy == "multimodal":
                        async for ev in stream_multimodal_query(driver, req.question, top_k, req.use_hyde, req.hyde_alpha, resolve_retrieval_doc_id(req.question, req.doc_hints), req.history or [], req.image_context or "", t_start, user_id, department): yield ev
                        return
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
                                history_msgs = trim_conversation_history_for_question(req.question, req.history, max_rounds=3)
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
                            log_source_doc_ids("counterfactual", cf_sections)
                            yield f"data: {json.dumps({'type': 'status', 'content': '推理中...'}, ensure_ascii=False)}\n\n"
                            full_answer = ""
                            try:
                                async for delta in get_llm_service().stream_chat(cf_messages, timeout=int(getattr(app_settings, "LLM_STREAM_TIMEOUT", 120))):
                                    delta = clean_stream_chunk(delta)
                                    if not delta:
                                        continue
                                    delta = clean_llm_response(delta)
                                    full_answer += delta
                                    yield f"data: {json.dumps({'type': 'delta', 'content': delta}, ensure_ascii=False)}\n\n"
                            except Exception as e:
                                logger.exception("counterfactual stream_chat 失败")
                                yield _error_event(e)
                                yield "data: [DONE]\n\n"
                                return
                            latency_ms = int((time.time() - t_start) * 1000)
                            full_answer = finalize_answer_text(full_answer, cf_sections, req.question)
                            emit_generation_record(strategy="counterfactual", question=req.question, answer=full_answer, latency_ms=latency_ms, user_id=user_id, department=department, model_name=get_llm_service().model_name)
                            fu = await _emit_follow_ups(req.question, full_answer, [s.get("doc_id") for s in cf_sections if s.get("doc_id")])
                            if fu:
                                yield f"data: {fu}\n\n"
                            yield "data: [DONE]\n\n"
                            return
                        except Exception as e:
                            logger.exception("反事实查询失败，降级到标准检索")
                    if req.strategy in ("parallel", "parallel_rrf", "hybrid_es", "sequential", "gnn", "graph_augmented"):
                        try:
                            compare_events = await build_compare_stream_events(
                                question=req.question,
                                driver=driver,
                                top_k=top_k,
                                t_start=t_start,
                                user_id=user_id,
                                department=department,
                                strategy=req.strategy,
                                use_hyde=req.use_hyde,
                                hyde_alpha=req.hyde_alpha,
                            )
                            if compare_events:
                                for event in compare_events:
                                    yield event
                                return
                        except Exception as e:
                            logger.warning("比较题专用检索失败，回退到通用检索: %s", e)
                    if req.use_hyde:
                        yield emit_status_event("增强模式：生成假设答案...")
                    _t_retrieval = time.time()
                    retrieval_doc_id = resolve_retrieval_doc_id(req.question, req.doc_hints)
                    sections, ft_score_map, expansion_info = await asyncio.to_thread(
                        do_retrieval,
                        driver, req.question, req.strategy, top_k,
                        req.use_hyde, req.hyde_alpha, retrieval_doc_id, True,
                    )
                    _retrieval_ms = int((time.time() - t_start) * 1000)
                    logger.info("[timing] 检索完成 t=%.2fs", time.time() - t_start)
                    if expansion_info:
                        yield f"data: {json.dumps({'type': 'expansion', 'content': expansion_info}, ensure_ascii=False)}\n\n"
                    sources = serialize_sources(sections, ft_score_map)
                    yield f"data: {json.dumps({'type': 'sources', 'content': sources}, ensure_ascii=False)}\n\n"
                    log_source_doc_ids("检索", sections)
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
                    _qtype, _handler, _type_label = get_question_handler_for(req.question)
                    if _type_label: yield emit_status_event(_type_label)
                    messages = [
                        {
                            "role":    "system",
                            "content": (
                                "你是一个航空制造工艺规范专家助手。请根据提供的规范内容，用中文准确回答问题。"
                                "回答时优先使用来源中的直接定义和描述，不要过多展开次要细节。"
                                "如果问题询问'特性'或'性质'，优先引用定义类章节（术语定义、基本要求章节），而不是参数表格。"
                                "如果来源中出现 'soft and ductile paste'、'solid and elastic rubber' 之类表述，可直接概括为'粘性和弹性'。"
                                "重要：规范编号必须与来源章节完全一致，不得自行修改或补全。"
                                "如果问题与之前的对话相关，请结合上下文回答。"
                                + (" " + _handler.system_addon() if _handler.system_addon() else "")
                            ),
                        }
                    ]
                    for h in trim_conversation_history_for_question(req.question, req.history, max_rounds=3):
                        messages.append({"role": h.get("role", "user"), "content": h.get("content", "")})
                    if req.image_context:
                        context = f"{context}\n\n{req.image_context}"
                    user_text = f"## 相关规范内容\n\n{context}\n\n## 问题\n\n{req.question}" + _handler.user_suffix()
                    messages.append({"role": "user", "content": user_text})
                    full_answer = ""
                    try:
                        async for delta in stream_with_first_token_logging(
                            get_llm_service(),
                            messages,
                            timeout=int(getattr(app_settings, "LLM_STREAM_TIMEOUT", 120)),
                            max_tokens=answer_max_tokens,
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
                            delta = clean_stream_chunk(delta)
                            if not delta:
                                continue
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
                    full_answer = finalize_answer_text(full_answer, sections, req.question)
                    emit_generation_record(strategy=req.strategy, question=req.question, answer=full_answer, latency_ms=latency_ms, user_id=user_id, department=department, model_name=get_llm_service().model_name)
                    if _q_emb and full_answer.strip():
                        try:
                            from ...services import semantic_cache
                            doc_ids = list({s["doc_id"] for s in sources if s.get("doc_id")})
                            await asyncio.to_thread(
                                semantic_cache.store,
                                _q_emb, req.strategy or "parallel", full_answer,
                                sources, cache_question[:200], doc_ids,
                            )
                        except Exception as _se:
                            logger.debug("语义缓存写入失败（跳过）: %s", _se)
                    yield build_metrics_event(latency_ms, _retrieval_ms, len(sections), len(sources))
                    fu = await _emit_follow_ups(req.question, full_answer, [s.get("doc_id") for s in sections if s.get("doc_id")])
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
    return StreamingResponse(generate(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"})
