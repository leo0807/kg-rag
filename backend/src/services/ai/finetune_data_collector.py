"""
I8.1: Collect high-quality Q&A pairs from user feedback and eval results for fine-tuning.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class FinetuneDataCollector:
    """Aggregates training examples from feedback, evaluations, and user corrections."""

    # ── Feedback collection ──────────────────────────────────────────────────

    async def collect_from_feedback(
        self,
        db: AsyncSession,
        min_rating: int = 4,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """Return positive examples from 4-5 star user feedback."""
        try:
            from sqlalchemy import text
            result = await db.execute(text("""
                SELECT q.question, q.answer, f.rating, f.comment
                FROM   qa_feedback f
                JOIN   qa_logs     q ON q.id = f.qa_log_id
                WHERE  f.rating >= :min_rating
                  AND  q.question IS NOT NULL
                  AND  q.answer   IS NOT NULL
                ORDER  BY f.created_at DESC
                LIMIT  :limit
            """), {"min_rating": min_rating, "limit": limit})
            rows = result.fetchall()
        except Exception as e:
            logger.warning("collect_from_feedback failed: %s", e)
            return []

        return [
            {"instruction": r.question, "output": r.answer,
             "input": "", "source": "feedback", "rating": r.rating}
            for r in rows
        ]

    async def collect_from_eval(
        self,
        db: AsyncSession,
        limit: int = 500,
    ) -> List[Dict[str, Any]]:
        """Return incorrectly-answered eval items with their reference answers."""
        try:
            from sqlalchemy import text
            result = await db.execute(text("""
                SELECT ei.question, ei.reference_answer, er.predicted_answer
                FROM   eval_results er
                JOIN   eval_items   ei ON ei.id = er.item_id
                WHERE  er.score < 0.6
                  AND  ei.reference_answer IS NOT NULL
                ORDER  BY er.created_at DESC
                LIMIT  :limit
            """), {"limit": limit})
            rows = result.fetchall()
        except Exception as e:
            logger.warning("collect_from_eval failed: %s", e)
            return []

        return [
            {"instruction": r.question, "output": r.reference_answer,
             "input": "", "source": "eval_correction",
             "rejected": r.predicted_answer}
            for r in rows
        ]

    async def collect_from_corrections(
        self,
        db: AsyncSession,
        limit: int = 500,
    ) -> List[Dict[str, Any]]:
        """Return user-corrected answers."""
        try:
            from sqlalchemy import text
            result = await db.execute(text("""
                SELECT original_question, corrected_answer, original_answer
                FROM   user_corrections
                WHERE  corrected_answer IS NOT NULL
                ORDER  BY created_at DESC
                LIMIT  :limit
            """), {"limit": limit})
            rows = result.fetchall()
        except Exception as e:
            logger.warning("collect_from_corrections failed: %s", e)
            return []

        return [
            {"instruction": r.original_question, "output": r.corrected_answer,
             "input": "", "source": "user_correction",
             "rejected": r.original_answer}
            for r in rows
        ]

    async def export_for_finetuning(
        self,
        db: AsyncSession,
        output_path: str,
        fmt: str = "alpaca",
        min_rating: int = 4,
    ) -> Dict[str, Any]:
        """Collect all sources and write a JSONL/Alpaca/ShareGPT file."""
        examples: List[Dict[str, Any]] = []
        examples += await self.collect_from_feedback(db, min_rating=min_rating)
        examples += await self.collect_from_eval(db)
        examples += await self.collect_from_corrections(db)

        # Deduplicate on instruction text
        seen: set[str] = set()
        deduped = []
        for ex in examples:
            key = ex["instruction"][:200]
            if key not in seen:
                seen.add(key)
                deduped.append(ex)

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        if fmt == "alpaca":
            data = [
                {"instruction": e["instruction"], "input": e.get("input", ""),
                 "output": e["output"]}
                for e in deduped
            ]
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        elif fmt == "sharegpt":
            data = [
                {"conversations": [
                    {"from": "human", "value": e["instruction"]},
                    {"from": "gpt",   "value": e["output"]},
                ]}
                for e in deduped
            ]
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        else:  # jsonl
            with open(output_path, "w", encoding="utf-8") as f:
                for e in deduped:
                    f.write(json.dumps(e, ensure_ascii=False) + "\n")

        logger.info("导出微调数据 %d 条 → %s (format=%s)", len(deduped), output_path, fmt)
        return {"total": len(deduped), "path": output_path, "format": fmt}


finetune_data_collector = FinetuneDataCollector()
