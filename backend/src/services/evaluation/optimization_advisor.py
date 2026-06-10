"""
Optimization advisor — generates actionable improvement suggestions
based on error analysis of an eval run.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.eval_models import EvalErrorAnalysis, EvalQuestion, EvalResult, EvalRun
from .error_analyzer import (
    REASON_FORMAT_MISMATCH, REASON_INSUFFICIENT_EVD, REASON_LLM_HALLUCINATION,
    REASON_NO_SOURCE, REASON_OPTION_PARSE, REASON_WRONG_DOC,
)

logger = logging.getLogger(__name__)

PRIORITY_SCORE = {"high": 3, "medium": 2, "low": 1}


@dataclass
class Suggestion:
    id: str
    category: str           # 检索召回 / 数据质量 / Prompt优化 / 文档限定
    priority: str           # high / medium / low
    title: str
    description: str
    affected_questions: list[str] = field(default_factory=list)
    action_items: list[str] = field(default_factory=list)
    auto_applicable: bool = False
    apply_action: Optional[str] = None  # "update_synonyms" / "create_prompt_version"

    @property
    def priority_score(self) -> int:
        return PRIORITY_SCORE.get(self.priority, 1)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "category": self.category, "priority": self.priority,
            "title": self.title, "description": self.description,
            "affected_questions": self.affected_questions,
            "action_items": self.action_items,
            "auto_applicable": self.auto_applicable,
            "apply_action": self.apply_action,
        }


async def generate_suggestions(run_id: str, db: AsyncSession) -> list[Suggestion]:
    run = await db.get(EvalRun, run_id)
    if not run:
        return []

    analyses = (await db.execute(
        select(EvalErrorAnalysis).where(EvalErrorAnalysis.run_id == run_id)
    )).scalars().all()

    if not analyses:
        return []

    total_errors = len(analyses)
    by_reason: dict[str, list[EvalErrorAnalysis]] = {}
    for a in analyses:
        by_reason.setdefault(a.error_reason, []).append(a)

    suggestions: list[Suggestion] = []
    sid = 0

    def _next_id() -> str:
        nonlocal sid
        sid += 1
        return f"sug-{run_id[:8]}-{sid:03d}"

    # ── Rule 1: Missing retrieval ─────────────────────────────────────
    no_src = by_reason.get(REASON_NO_SOURCE, [])
    if len(no_src) > max(3, total_errors * 0.15):
        affected = [a.result_id for a in no_src[:10]]
        suggestions.append(Suggestion(
            id=_next_id(), category="检索召回", priority="high",
            title="检索召回率偏低",
            description=f"{len(no_src)} 道题未能检索到相关章节（占错误 {len(no_src)/total_errors:.0%}）",
            affected_questions=affected,
            action_items=["在 synonyms.json 中补充题目关键词同义词",
                          "增大 top_k 值（当前: " + str(run.config.get("top_k", 5)) + "，建议: 8-10）",
                          "对高频错误文档重新解析章节"],
            auto_applicable=False,
        ))

    # ── Rule 2: Wrong document ───────────────────────────────────────
    wrong_doc = by_reason.get(REASON_WRONG_DOC, [])
    if len(wrong_doc) > max(2, total_errors * 0.10):
        affected = [a.result_id for a in wrong_doc[:10]]
        # Find which docs are being confused
        source_docs = set()
        for a in wrong_doc:
            if "sources_count" in (a.details or {}):
                pass
        suggestions.append(Suggestion(
            id=_next_id(), category="文档限定", priority="high",
            title="跨文档混淆",
            description=f"{len(wrong_doc)} 道题检索到错误文档",
            affected_questions=affected,
            action_items=["在评测配置中指定 source_doc_id 限制检索范围",
                          "检查文档分段是否导致章节混淆",
                          "为相似文档增加区分性标签"],
            auto_applicable=False,
        ))

    # ── Rule 3: LLM hallucination ────────────────────────────────────
    halluc = by_reason.get(REASON_LLM_HALLUCINATION, [])
    if len(halluc) > max(2, total_errors * 0.10):
        suggestions.append(Suggestion(
            id=_next_id(), category="Prompt优化", priority="medium",
            title="LLM答案编造",
            description=f"{len(halluc)} 道题存在疑似幻觉",
            affected_questions=[a.result_id for a in halluc[:10]],
            action_items=["在 Prompt 中强化「只能基于给定上下文作答」约束",
                          "降低 temperature 至 0.0-0.1",
                          "创建新版本 Prompt 并重跑评测对比"],
            auto_applicable=True,
            apply_action="create_prompt_version",
        ))

    # ── Rule 4: Option parsing error ─────────────────────────────────
    parse_err = by_reason.get(REASON_OPTION_PARSE, [])
    if len(parse_err) > max(2, total_errors * 0.08):
        suggestions.append(Suggestion(
            id=_next_id(), category="Prompt优化", priority="medium",
            title="选项解析格式问题",
            description=f"{len(parse_err)} 道题答案格式不符合预期",
            affected_questions=[a.result_id for a in parse_err[:10]],
            action_items=["更新选项解析 Prompt，明确输出格式为单个字母",
                          "在后处理中增加格式归一化"],
            auto_applicable=False,
        ))

    # ── Rule 5: Insufficient evidence ────────────────────────────────
    insuff = by_reason.get(REASON_INSUFFICIENT_EVD, [])
    if len(insuff) > max(3, total_errors * 0.20):
        suggestions.append(Suggestion(
            id=_next_id(), category="检索召回", priority="medium",
            title="检索内容相关性不足",
            description=f"{len(insuff)} 道题检索到内容但质量不够",
            affected_questions=[a.result_id for a in insuff[:10]],
            action_items=["启用 Reranker 或提高 Reranker 阈值",
                          "尝试使用 HyDE 增强检索",
                          "考虑切换到 graph_enhanced 策略"],
            auto_applicable=False,
        ))

    # ── Rule 6: Low overall accuracy ─────────────────────────────────
    if (run.accuracy or 0) < 0.60:
        suggestions.append(Suggestion(
            id=_next_id(), category="综合", priority="high",
            title="整体准确率偏低",
            description=f"当前准确率 {(run.accuracy or 0):.1%}，建议系统性优化",
            action_items=["对比其他检索策略（graph/multi_hop）",
                          "检查评测数据集质量（是否有标注错误）",
                          "分析各难度层级的准确率分布"],
            auto_applicable=False,
        ))

    return sorted(suggestions, key=lambda s: -s.priority_score)


async def get_suggestions_api(run_id: str, db: AsyncSession) -> list[dict]:
    suggestions = await generate_suggestions(run_id, db)
    return [s.to_dict() for s in suggestions]
