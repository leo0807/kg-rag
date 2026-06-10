"""
Error analyzer — categorizes wrong answers into structured reasons.
Runs after an eval run completes.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.eval_models import EvalErrorAnalysis, EvalQuestion, EvalResult, EvalRun

logger = logging.getLogger(__name__)

REASON_NO_SOURCE         = "未检索到相关章节"
REASON_WRONG_DOC         = "检索到错误文档"
REASON_INSUFFICIENT_EVD  = "证据不足"
REASON_LLM_HALLUCINATION = "LLM编造内容"
REASON_OPTION_PARSE      = "选项解析错误"
REASON_FORMAT_MISMATCH   = "答案格式不匹配"
REASON_AMBIGUOUS         = "问题歧义"
REASON_OUT_OF_SCOPE      = "超出规范范围"
REASON_UNKNOWN           = "其他"


@dataclass
class ErrorAnalysis:
    result_id: str
    run_id: str
    error_reason: str
    confidence: float
    details: dict
    suggestions: list[str]


def _classify(result: EvalResult, question: EvalQuestion) -> ErrorAnalysis:
    sources = result.sources or []
    reasoning = (result.reasoning or "").lower()
    predicted = (result.predicted_answer or "").strip()

    # Rule-based classification (fast, deterministic)
    if result.error_type == "no_answer" or not predicted:
        if not sources:
            reason, conf = REASON_NO_SOURCE, 0.90
        else:
            reason, conf = REASON_INSUFFICIENT_EVD, 0.75
    elif not sources:
        reason, conf = REASON_NO_SOURCE, 0.85
    elif any(k in reasoning for k in ("未找到", "没有找到", "无相关", "不包含")):
        reason, conf = REASON_NO_SOURCE, 0.80
    elif question.source_doc_id and sources:
        source_docs = [s.split("§")[0].strip() if isinstance(s, str) else "" for s in sources]
        if question.source_doc_id and not any(question.source_doc_id in d for d in source_docs):
            reason, conf = REASON_WRONG_DOC, 0.80
        else:
            reason, conf = REASON_INSUFFICIENT_EVD, 0.60
    elif question.question_type == "mcq" and question.options:
        valid_labels = {k.upper() for k in question.options}
        if predicted.upper() not in valid_labels:
            reason, conf = REASON_OPTION_PARSE, 0.85
        else:
            reason, conf = REASON_LLM_HALLUCINATION, 0.55
    else:
        reason, conf = REASON_UNKNOWN, 0.40

    # Suggestions by reason
    suggestions: dict[str, list[str]] = {
        REASON_NO_SOURCE:        ["补充同义词或近义表达", "重新解析相关章节"],
        REASON_WRONG_DOC:        ["强化文档限定逻辑", "检查文档 ID 映射"],
        REASON_INSUFFICIENT_EVD: ["增大 top_k 参数", "调整 Reranker 阈值"],
        REASON_LLM_HALLUCINATION:["降低 temperature", "在 Prompt 中强调只用给定上下文作答"],
        REASON_OPTION_PARSE:     ["优化选项解析 Prompt", "统一选项格式"],
        REASON_FORMAT_MISMATCH:  ["规范化答案格式"],
        REASON_UNKNOWN:          ["人工核查该题"],
    }

    return ErrorAnalysis(
        result_id=result.id, run_id=result.run_id,
        error_reason=reason, confidence=conf,
        details={"predicted": predicted, "correct": question.correct_answer,
                 "sources_count": len(sources)},
        suggestions=suggestions.get(reason, []),
    )


async def analyze_run_errors(run_id: str, db: AsyncSession) -> int:
    """Classify all wrong answers in a run. Returns count of errors analyzed."""
    results = (await db.execute(
        select(EvalResult).where(EvalResult.run_id == run_id, EvalResult.is_correct == False)  # noqa: E712
    )).scalars().all()
    if not results:
        return 0

    qids = {r.question_id for r in results}
    questions = {q.id: q for q in (await db.execute(
        select(EvalQuestion).where(EvalQuestion.id.in_(qids))
    )).scalars().all()}

    # Delete old analysis for this run
    from sqlalchemy import delete
    await db.execute(delete(EvalErrorAnalysis).where(EvalErrorAnalysis.run_id == run_id))

    for result in results:
        q = questions.get(result.question_id)
        if not q:
            continue
        analysis = _classify(result, q)
        db.add(EvalErrorAnalysis(
            id=str(uuid.uuid4()),
            result_id=analysis.result_id,
            run_id=analysis.run_id,
            error_reason=analysis.error_reason,
            confidence=analysis.confidence,
            details=analysis.details,
            suggestions=analysis.suggestions,
        ))

    await db.commit()
    return len(results)


async def trigger_error_analysis(run_id: str) -> dict:
    """Callable from API — runs analysis and returns summary."""
    from ...db.session import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        count = await analyze_run_errors(run_id, db)
        rows = (await db.execute(
            select(EvalErrorAnalysis).where(EvalErrorAnalysis.run_id == run_id)
        )).scalars().all()
    by_reason: dict[str, int] = {}
    for a in rows:
        by_reason[a.error_reason] = by_reason.get(a.error_reason, 0) + 1
    return {"analyzed": count, "by_reason": by_reason}
