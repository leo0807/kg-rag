"""
src/services/quality/feedback_optimizer.py
反馈驱动优化器：分析高错误率章节并产出改进建议。
"""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

ERROR_THRESHOLD = 0.4   # 错误率超过此阈值触发分析
MIN_SAMPLES     = 3     # 样本量不足时跳过


@dataclass
class OptimizationSuggestion:
    chunk_id:   str
    error_rate: float
    sample_count: int
    patterns:   list[str]
    suggestions: list[str]


class FeedbackDrivenOptimizer:
    """分析 query_feedback 中的错误模式，产出优化建议（不自动修改数据）。"""

    async def analyze_problematic_chunks(self, db) -> list[OptimizationSuggestion]:
        from sqlalchemy import select
        from ...routers.feedback import QueryFeedback

        neg_result = await db.execute(
            select(QueryFeedback.sources, QueryFeedback.error_types, QueryFeedback.accuracy)
            .where(
                (QueryFeedback.rating == -1)
                | (QueryFeedback.accuracy.in_(["partial", "wrong"]))
            )
        )
        pos_result = await db.execute(
            select(QueryFeedback.sources)
            .where(QueryFeedback.rating == 1)
        )

        chunk_neg:   dict[str, int]        = defaultdict(int)
        chunk_pos:   dict[str, int]        = defaultdict(int)
        chunk_errors: dict[str, list[str]] = defaultdict(list)

        for src_json, et_json, _ in neg_result.all():
            error_types = json.loads(et_json or "[]")
            for src in json.loads(src_json or "[]"):
                cid = src.get("chunk_id") or src.get("doc_id", "")
                if cid:
                    chunk_neg[cid] += 1
                    chunk_errors[cid].extend(error_types)

        for (src_json,) in pos_result.all():
            for src in json.loads(src_json or "[]"):
                cid = src.get("chunk_id") or src.get("doc_id", "")
                if cid:
                    chunk_pos[cid] += 1

        suggestions: list[OptimizationSuggestion] = []
        all_chunks = set(chunk_neg) | set(chunk_pos)

        for cid in all_chunks:
            neg   = chunk_neg.get(cid, 0)
            pos   = chunk_pos.get(cid, 0)
            total = neg + pos
            if total < MIN_SAMPLES:
                continue
            rate = neg / total
            if rate < ERROR_THRESHOLD:
                continue

            patterns   = self._detect_patterns(chunk_errors[cid])
            suggestion = self._build_suggestions(cid, patterns)
            suggestions.append(OptimizationSuggestion(
                chunk_id     = cid,
                error_rate   = round(rate, 3),
                sample_count = total,
                patterns     = patterns,
                suggestions  = suggestion,
            ))

        suggestions.sort(key=lambda s: -s.error_rate)
        logger.info("FeedbackOptimizer: %d 高错误率章节", len(suggestions))
        return suggestions

    def _detect_patterns(self, error_type_list: list[str]) -> list[str]:
        counts: dict[str, int] = defaultdict(int)
        for t in error_type_list:
            counts[t] += 1
        dominant = [t for t, c in counts.items() if c >= 2]
        patterns = []
        if "wrong_doc" in dominant:
            patterns.append("wrong_doc_reference")
        if "hallucination" in dominant:
            patterns.append("hallucination")
        if "value_error" in dominant:
            patterns.append("numeric_parameter_error")
        if "incomplete" in dominant:
            patterns.append("incomplete_answer")
        if "irrelevant_source" in dominant:
            patterns.append("irrelevant_retrieval")
        if not patterns:
            patterns.append("general_quality_issue")
        return patterns

    def _build_suggestions(self, chunk_id: str, patterns: list[str]) -> list[str]:
        suggestions = []
        if "wrong_doc_reference" in patterns:
            suggestions.append(f"检查 {chunk_id} 的跨文档引用链，确认 REFERENCES 边指向正确")
        if "hallucination" in patterns:
            suggestions.append(f"为 {chunk_id} 所在文档补充同义词，减少模型编造风险")
        if "numeric_parameter_error" in patterns:
            suggestions.append(f"检查 {chunk_id} 的 Constraint 节点数值是否被 OCR 错误截断")
        if "irrelevant_retrieval" in patterns:
            suggestions.append(f"降低 {chunk_id} 的向量相似度权重，或检查 chunk 切割边界")
        if "incomplete_answer" in patterns:
            suggestions.append(f"{chunk_id} 可能被切割过细，考虑合并相邻 chunk")
        return suggestions
