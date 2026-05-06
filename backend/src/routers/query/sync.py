"""
非流式查询接口
"""
import logging
import time
from fastapi import Depends, HTTPException, Request
from neo4j import Driver
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ...core.database import get_driver
from ...core.config import settings
from ...core.observability import send_generation
from ...services.ai.llm_service import get_llm_service
from ...services.infra.cache import get_cached_result, set_cached_result
from ...services.runtime.model_settings import load_effective_settings, use_runtime_settings
from ...db.models import User, PipelineConfig
from .models import QueryRequest, QueryResponse, QueryMetrics, SourceSection
from .core   import do_retrieval

# 已知模型每 1K token 成本 (USD: input, output)
_MODEL_PRICE: dict[str, tuple[float, float]] = {
    "gpt-4o":            (0.005,  0.015),
    "gpt-4o-mini":       (0.00015, 0.0006),
    "claude-3-5-sonnet": (0.003,  0.015),
    "claude-3-haiku":    (0.00025, 0.00125),
    "qwen2.5-7b":        (0.0,    0.0),
}

def _calc_cost(model: str, prompt_tok: int, completion_tok: int) -> float:
    key = next((k for k in _MODEL_PRICE if k in model.lower()), None)
    if not key:
        return 0.0
    p_in, p_out = _MODEL_PRICE[key]
    return round((prompt_tok * p_in + completion_tok * p_out) / 1000, 6)

logger = logging.getLogger(__name__)


def _sections_to_sources(sections: list[dict], score_map: dict) -> list[SourceSection]:
    return [
        SourceSection(
            chunk_id=s["chunk_id"], doc_id=s["doc_id"],
            number=s.get("number") or "", title=s.get("title") or "",
            score=round(s.get("rerank_score") or score_map.get(s["chunk_id"], 0.0), 4),
            page_idx=s.get("page_idx"),
            bbox=s.get("bbox"),
            source_type=s.get("source_type", []),
            retrieval_trace=s.get("retrieval_trace", []),
            is_graph_expanded=bool(s.get("is_graph_expanded")),
            is_vector_hit=bool(s.get("is_vector_hit")),
            is_fulltext_hit=bool(s.get("is_fulltext_hit")),
            is_gnn_hit=bool(s.get("is_gnn_hit")),
            content_type=s.get("content_type", "section"),
            table_id=s.get("table_id"),
            row_index=s.get("row_index"),
            headers=s.get("headers") or [],
            row_data=s.get("row_data"),
        )
        for s in sections
    ]


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

        cached = get_cached_result(req.question, req.strategy, top_k)
        if cached:
            return QueryResponse(**cached)

        start = time.time()

        # ── 自定义链路（用户有默认 pipeline 配置时走此路径）────────────────
        if db and user_id and req.strategy not in ("multi_hop",):
            pipeline_cfg = await _get_default_pipeline(user_id, db)
            if pipeline_cfg:
                try:
                    answer, sections = await _run_pipeline(pipeline_cfg, req.question, driver, user_id)
                    sources = _sections_to_sources(sections, {})
                    latency_ms = int((time.time() - start) * 1000)
                    send_generation(
                        name="graphrag-query", model=get_llm_service().model_name,
                        input_messages=[{"role": "user", "content": req.question}],
                        output=answer, latency_ms=latency_ms, strategy="pipeline",
                        user_id=user_id, department=department, question_preview=req.question,
                    )
                    set_cached_result(req.question, "pipeline", top_k,
                                      {"answer": answer, "sources": [s.model_dump() for s in sources]})
                    return QueryResponse(answer=answer, sources=sources)
                except Exception as e:
                    logger.warning("自定义链路执行失败，降级到标准策略: %s", e)

        # ── 标准四策略路径（fallback）────────────────────────────────────────
        if req.strategy == "multi_hop":
            try:
                from ...services.retrieval.multi_hop import multi_hop_query
                answer, mh_sections, _steps = multi_hop_query(req.question, driver, top_k=top_k)
                sources = _sections_to_sources(mh_sections, {})
                latency_ms = int((time.time() - start) * 1000)
                send_generation(
                    name="graphrag-query", model=get_llm_service().model_name,
                    input_messages=[{"role": "user", "content": req.question}],
                    output=answer, latency_ms=latency_ms, strategy="multi_hop",
                    user_id=user_id, department=department, question_preview=req.question,
                )
                set_cached_result(req.question, req.strategy, top_k,
                                  {"answer": answer, "sources": [s.model_dump() for s in sources]})
                return QueryResponse(answer=answer, sources=sources)
            except Exception as e:
                logger.warning("多跳推理失败，降级: %s", e)

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
            raw_context = "\n\n".join(
                f"[{s['doc_id']} §{s['number']}] {s['title']}\n{s['content']}"
                for s in sections
            )
            context = (conflict_notes + "\n\n" + raw_context) if conflict_notes else raw_context
            try:
                from ...services.ai.llm import generate_answer_with_usage
                t_llm = time.time()
                answer, usage = generate_answer_with_usage(
                    question=req.question, context=context, history=req.history,
                )
                llm_ms            = int((time.time() - t_llm) * 1000)
                prompt_tokens     = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)
            except Exception as e:
                logger.warning("LLM 失败: %s", e)
                answer = f"检索到 {len(sections)} 个相关章节：\n\n{context[:2000]}"

        sources = _sections_to_sources(sections, ft_score_map)
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

        send_generation(
            name="graphrag-query", model=model_name,
            input_messages=[{"role": "user", "content": req.question}],
            output=answer, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
            latency_ms=total_ms, strategy=req.strategy,
            user_id=user_id, department=department, question_preview=req.question,
        )
        set_cached_result(req.question, req.strategy, top_k,
                          {"answer": answer, "sources": [s.model_dump() for s in sources],
                           "expansion_info": expansion_info})
        return QueryResponse(answer=answer, sources=sources, expansion_info=expansion_info,
                             metrics=metrics)
