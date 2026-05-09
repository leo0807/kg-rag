"""
非流式查询接口
"""
import logging
import re
import time
from fastapi import Depends, HTTPException, Request
from neo4j import Driver
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ...core.database import get_driver
from ...core.config import settings
from ...services.ai.llm import clean_llm_response
from ...services.ai.llm_service import get_llm_service
from ...services.infra.cache import get_cached_result, set_cached_result
from ...services.runtime.model_settings import load_effective_settings, use_runtime_settings
from ...db.models import User, PipelineConfig
from .query_utils import (
    emit_generation_record,
    extract_numeric_answer,
    finalize_answer_text,
    log_source_doc_ids,
    sections_to_sources,
)
from .models import QueryRequest, QueryResponse, QueryMetrics, SourceSection
from .core   import do_retrieval
from .clarification_utils import build_clarification_payload, detect_clarification
from .context_utils import build_llm_context, reorder_sources_for_llm
logger = logging.getLogger(__name__)
async def _get_default_pipeline(user_id: str, db: AsyncSession) -> dict | None:
    """取用户默认链路配置，无则返回 None。"""
    try:
        result = await db.execute(
            select(PipelineConfig).where(
                PipelineConfig.user_id == user_id,
                PipelineConfig.is_default.is_(True),
                PipelineConfig.is_active.is_(True),
            )
        )
        cfg = result.scalar_one_or_none()
        if cfg and cfg.nodes:
            return {"nodes": cfg.nodes, "edges": cfg.edges, "params": cfg.params}
    except Exception as e:
        logger.warning("获取默认链路配置失败: %s", e)
    return None
async def _run_pipeline(
    pipeline_cfg: dict,
    question: str,
    driver: Driver,
    user_id: str,
) -> tuple[str, list[dict]]:
    """执行自定义链路，返回 (answer, sections)。"""
    from ...services.pipeline_executor import PipelineExecutor
    executor = PipelineExecutor(pipeline_cfg, driver)
    result = await executor.execute(question, user_id=user_id)
    return result.get("answer", ""), result.get("candidates", [])
async def query_sync(
    request:      Request,
    req:          QueryRequest,
    driver:       Driver = Depends(get_driver),
    current_user: User | None = None,
    db:           AsyncSession | None = None,
):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="question 不能为空")
    effective_settings = await load_effective_settings(db, current_user.id if current_user else None)
    with use_runtime_settings(effective_settings):
        top_k      = req.top_k or 5
        user_id    = current_user.id         if current_user else ""
        department = current_user.department if current_user else ""
    clarification = await detect_clarification(
        req.question,
        driver,
        skip=req.skip_clarification,
    )
    if clarification.get("needs_clarification"):
        return QueryResponse(**build_clarification_payload(req.question, clarification))
    cached = get_cached_result(req.question, req.strategy, top_k)
    if cached:
        return QueryResponse(**cached)
    start = time.time()
    # ── 自定义链路（用户有默认 pipeline 配置时走此路径）────────────────
    if db and user_id and req.strategy == "pipeline":
        pipeline_cfg = await _get_default_pipeline(user_id, db)
        if pipeline_cfg:
            try:
                answer, sections = await _run_pipeline(
                    pipeline_cfg, req.question, driver, user_id
                )
                answer = finalize_answer_text(answer, sections, req.question)
                sources = sections_to_sources(sections, {})
                log_source_doc_ids("Pipeline", sections)
                latency_ms = int((time.time() - start) * 1000)
                emit_generation_record(
                    strategy="pipeline",
                    question=req.question,
                    answer=answer,
                    latency_ms=latency_ms,
                    user_id=user_id,
                    department=department,
                    model_name=get_llm_service().model_name,
                )
                set_cached_result(
                    req.question,
                    "pipeline",
                    top_k,
                    {"answer": answer, "sources": [s.model_dump() for s in sources]},
                )
                return QueryResponse(answer=answer, sources=sources)
            except Exception as e:
                logger.warning("自定义链路执行失败，降级到标准策略: %s", e)

    # ── 标准四策略路径（fallback）────────────────────────────────────────
    if req.strategy == "multi_hop":
        try:
            from ...services.retrieval.multi_hop import multi_hop_query
            answer, mh_sections, _steps = multi_hop_query(req.question, driver, top_k=top_k)
            answer = finalize_answer_text(answer, mh_sections, req.question)
            sources = sections_to_sources(mh_sections, {})
            log_source_doc_ids("Multi-hop", mh_sections)
            latency_ms = int((time.time() - start) * 1000)
            emit_generation_record(
                strategy="multi_hop",
                question=req.question,
                answer=answer,
                latency_ms=latency_ms,
                user_id=user_id,
                department=department,
                model_name=get_llm_service().model_name,
            )
            set_cached_result(req.question, req.strategy, top_k,
                              {"answer": answer, "sources": [s.model_dump() for s in sources]})
            return QueryResponse(answer=answer, sources=sources)
        except Exception as e:
            logger.warning("多跳推理失败，降级: %s", e)

    if req.strategy == "agent":
        try:
            from ...services.agent.agent_executor import AgentExecutor
            from ...services.agent.tool_executor import ToolExecutor
            tool_executor = ToolExecutor(driver)
            executor = AgentExecutor(get_llm_service(), tool_executor)
            result = await executor.run(req.question)
            answer = finalize_answer_text(result.get("answer", ""), result.get("sources", []), req.question)
            sources = sections_to_sources(result.get("sources", []), {})
            images = result.get("images", []) or []
            log_source_doc_ids("Agent", result.get("sources", []))
            latency_ms = int((time.time() - start) * 1000)
            emit_generation_record(
                strategy="agent",
                question=req.question,
                answer=answer,
                latency_ms=latency_ms,
                user_id=user_id,
                department=department,
                model_name=get_llm_service().model_name,
            )
            set_cached_result(
                req.question,
                req.strategy,
                top_k,
                {
                    "answer": answer,
                    "sources": [s.model_dump() for s in sources],
                    "images": images,
                    "iterations": result.get("iterations"),
                    "strategy_used": result.get("strategy_used", "agent"),
                },
            )
            return QueryResponse(
                answer=answer,
                sources=sources,
                images=images,
                iterations=result.get("iterations"),
            )
        except Exception as e:
            logger.warning("Agent 推理失败，降级到标准检索: %s", e)

    t_retrieval = time.time()
    sections, ft_score_map, expansion_info = do_retrieval(driver, req.question, req.strategy, top_k)
    retrieval_ms = int((time.time() - t_retrieval) * 1000)

    # 注入规范冲突仲裁注释
    conflict_notes = ""
    if sections and db:
        try:
            from ...services.quality.conflict_arbiter import get_conflict_notes_for_chunks
            chunk_ids = [s["chunk_id"] for s in sections]
            conflict_notes = await get_conflict_notes_for_chunks(chunk_ids, db)
        except Exception:
            pass

    prompt_tokens = completion_tokens = 0
    llm_ms = 0
    if not sections:
        answer = "在知识库中未找到相关章节，请确认文件已入库。"
    else:
        llm_sections = reorder_sources_for_llm(sections, req.question)
        llm_context = build_llm_context(llm_sections)
        context = (conflict_notes + "\n\n" + llm_context) if conflict_notes else llm_context
        try:
            from ...services.ai.llm import generate_answer_with_usage
            t_llm = time.time()
            answer, usage = generate_answer_with_usage(
                question=req.question, context=context, history=req.history,
            )
            answer = clean_llm_response(answer)
            if "未找到相关信息" in answer:
                extracted = extract_numeric_answer(req.question, sections)
                if extracted:
                    answer = extracted
            answer = finalize_answer_text(answer, sections, req.question)
            llm_ms            = int((time.time() - t_llm) * 1000)
            prompt_tokens     = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
        except Exception as e:
            logger.warning("LLM 失败: %s", e)
            answer = f"检索到 {len(sections)} 个相关章节：\n\n{context[:2000]}"

    sources = sections_to_sources(sections, ft_score_map)
    log_source_doc_ids("检索", sections)
    answer = finalize_answer_text(answer, sections, req.question)
    total_ms = int((time.time() - start) * 1000)
    model_name = get_llm_service().model_name

    metrics = QueryMetrics(
        total_ms=total_ms,
        stages={"检索": retrieval_ms, "LLM生成": llm_ms},
        tokens={"prompt": prompt_tokens, "completion": completion_tokens,
                "total": prompt_tokens + completion_tokens},
        cost_usd=_calc_cost(model_name, prompt_tokens, completion_tokens),
        candidates_retrieved=len(sections),
        candidates_after_rerank=len(sources),
    )

    emit_generation_record(
        strategy=req.strategy,
        question=req.question,
        answer=answer,
        latency_ms=total_ms,
        user_id=user_id,
        department=department,
        model_name=model_name,
    )
    set_cached_result(req.question, req.strategy, top_k,
                      {"answer": answer, "sources": [s.model_dump() for s in sources],
                       "expansion_info": expansion_info})
    return QueryResponse(answer=answer, sources=sources, expansion_info=expansion_info,
                         metrics=metrics)
