"""K7.1: Extract design rules, critical factors, and anomaly patterns from simulation cases."""
from __future__ import annotations

import logging
import statistics
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class RuleExtractor:
    """Mine simulation case history for reusable engineering rules."""

    MIN_CASES_FOR_RULE = 3

    # ── Design rules ──────────────────────────────────────────────────────────
    async def extract_design_rules(self, db: AsyncSession) -> List[Dict]:
        from ...db.simulation_models import SimulationCase, SimulationResult

        cases = (await db.execute(select(SimulationCase).limit(500))).scalars().all()
        if len(cases) < self.MIN_CASES_FOR_RULE:
            return []

        rules: List[Dict] = []

        # Group by (domain, application)
        groups: Dict[str, List] = {}
        for c in cases:
            key = f"{c.domain}|{c.application}"
            groups.setdefault(key, []).append(c)

        for key, grp in groups.items():
            if len(grp) < self.MIN_CASES_FOR_RULE:
                continue
            domain, app = key.split("|", 1)

            # Gather results for this group
            result_rows = (await db.execute(
                select(SimulationResult).where(
                    SimulationResult.case_id.in_([c.id for c in grp])
                )
            )).scalars().all()

            if not result_rows:
                continue

            max_vals = [r.max_value for r in result_rows if r.max_value is not None]
            if not max_vals:
                continue

            avg = statistics.mean(max_vals)
            std = statistics.stdev(max_vals) if len(max_vals) > 1 else 0.0
            unit = result_rows[0].unit if result_rows else ""

            rules.append({
                "rule_type": "design",
                "title":     f"{domain}/{app} — 关键结果均值 {avg:.2f}{unit}，σ={std:.2f}",
                "condition": f"domain={domain}, application={app}",
                "recommendation": (
                    f"在 {app} 场景下，{domain} 分析中关键结果应控制在 "
                    f"{avg-2*std:.2f}~{avg+2*std:.2f}{unit} 范围内（2σ置信区间）"
                ),
                "confidence":   min(0.5 + 0.05 * len(grp), 0.95),
                "source_cases": [c.id for c in grp],
            })

        return rules

    # ── Critical factors ──────────────────────────────────────────────────────
    async def extract_critical_factors(self, db: AsyncSession) -> List[Dict]:
        from ...db.simulation_models import SimulationCase, SimulationResult

        cases = (await db.execute(select(SimulationCase).limit(200))).scalars().all()
        if len(cases) < self.MIN_CASES_FOR_RULE:
            return []

        # Gather all input keys and correlate with max result
        param_scores: Dict[str, float] = {}
        param_counts: Dict[str, int] = {}

        for c in cases:
            results = (await db.execute(
                select(SimulationResult).where(SimulationResult.case_id == c.id).limit(5)
            )).scalars().all()
            if not results:
                continue
            result_max = max((r.max_value or 0) for r in results)

            for k, v in (c.inputs or {}).items():
                try:
                    num = float(v)
                    param_scores[k] = param_scores.get(k, 0) + abs(num * result_max)
                    param_counts[k] = param_counts.get(k, 0) + 1
                except (TypeError, ValueError):
                    pass

        factors = [
            {
                "rule_type": "factor",
                "title": f"关键影响因子：{k}",
                "condition": f"参数 {k} 出现 {param_counts[k]} 次",
                "recommendation": f"在设计中应优先关注参数 {k} 的取值，其对仿真结果影响较大",
                "confidence": min(param_counts[k] / 10, 0.9),
                "source_cases": [],
            }
            for k in sorted(param_scores, key=lambda x: -param_scores[x])[:5]
            if param_counts.get(k, 0) >= self.MIN_CASES_FOR_RULE
        ]
        return factors

    # ── Anomaly patterns ──────────────────────────────────────────────────────
    async def extract_anomaly_patterns(self, db: AsyncSession) -> List[Dict]:
        from ...db.simulation_models import SimulationCase, SimulationResult

        # Find cases with failed results
        failed_results = (await db.execute(
            select(SimulationResult).where(SimulationResult.pass_status == "fail").limit(200)
        )).scalars().all()

        if len(failed_results) < self.MIN_CASES_FOR_RULE:
            return []

        case_ids = list({r.case_id for r in failed_results})
        cases = (await db.execute(
            select(SimulationCase).where(SimulationCase.id.in_(case_ids))
        )).scalars().all()

        input_keys: Dict[str, int] = {}
        for c in cases:
            for k in (c.inputs or {}):
                input_keys[k] = input_keys.get(k, 0) + 1

        top_keys = sorted(input_keys, key=lambda x: -input_keys[x])[:3]

        patterns = []
        for k in top_keys:
            vals = [str((c.inputs or {}).get(k, "")) for c in cases if k in (c.inputs or {})]
            if not vals:
                continue
            patterns.append({
                "rule_type": "anomaly",
                "title": f"参数 {k} 与仿真失败的关联模式",
                "condition": f"存在 {len(cases)} 个失败案例涉及参数 {k}",
                "recommendation": f"当 {k} 取值为 {', '.join(vals[:3])} 等情况时，注意仿真结果可能超标",
                "confidence": min(len(cases) / 20, 0.85),
                "source_cases": case_ids[:10],
            })

        return patterns

    # ── Save extracted rules ──────────────────────────────────────────────────
    async def save_rules(self, db: AsyncSession, rules: List[Dict]) -> int:
        from ...db.simulation_models import SimulationRule
        import uuid as _uuid

        saved = 0
        for r in rules:
            # Skip if similar title already exists
            existing = (await db.execute(
                select(SimulationRule).where(SimulationRule.title == r["title"]).limit(1)
            )).scalar_one_or_none()
            if existing:
                continue
            db.add(SimulationRule(
                id=str(_uuid.uuid4()),
                rule_type=r.get("rule_type", "design"),
                title=r["title"],
                condition=r.get("condition", ""),
                recommendation=r.get("recommendation", ""),
                confidence=r.get("confidence", 0.5),
                source_cases=r.get("source_cases", []),
                extracted_at=_now(),
            ))
            saved += 1

        if saved:
            await db.commit()
        return saved

    async def run_all(self, db: AsyncSession) -> Dict[str, int]:
        design_rules  = await self.extract_design_rules(db)
        factor_rules  = await self.extract_critical_factors(db)
        anomaly_rules = await self.extract_anomaly_patterns(db)

        all_rules = design_rules + factor_rules + anomaly_rules
        saved = await self.save_rules(db, all_rules)

        return {
            "design": len(design_rules),
            "factors": len(factor_rules),
            "anomalies": len(anomaly_rules),
            "saved": saved,
        }


rule_extractor = RuleExtractor()
