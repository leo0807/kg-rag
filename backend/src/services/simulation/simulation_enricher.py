"""K3.3: Enrich QA answers with relevant simulation cases and rules."""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# ── Parameter extraction patterns ─────────────────────────────────────────────
_PARAM_PATTERNS = [
    # temperature  e.g. "80℃"  "−20°C"
    (re.compile(r"(-?\d+(?:\.\d+)?)\s*[℃°C]"), "temperature"),
    # pressure  e.g. "0.3MPa"  "1.2 bar"
    (re.compile(r"(\d+(?:\.\d+)?)\s*(?:MPa|kPa|bar|psi)", re.I), "pressure"),
    # material  e.g. "Ti-6Al-4V"  "304不锈钢"
    (re.compile(r"(Ti-\d[A-Za-z0-9-]+|[A-Z]\d{3}[A-Za-z]*|[A-Z]{1,3}\d{3,4})"), "material"),
    # load type
    (re.compile(r"(疲劳|交变载荷|静载荷|冲击|蠕变|fatigue|cyclic)", re.I), "load_type"),
]

_DOMAIN_MAP = {
    "温度": "thermal", "热": "thermal", "冷却": "thermal",
    "应力": "structural", "疲劳": "structural", "强度": "structural",
    "流": "fluid", "压力": "fluid", "密封": "structural",
}


def _extract_params(question: str) -> Dict[str, Any]:
    params: Dict[str, Any] = {}
    for pattern, key in _PARAM_PATTERNS:
        m = pattern.search(question)
        if m:
            params[key] = m.group(1)
    # Detect domain
    for kw, domain in _DOMAIN_MAP.items():
        if kw in question:
            params["domain"] = domain
            break
    return params


def _format_case_summary(cases: List[Any]) -> str:
    lines = []
    for c in cases:
        name = getattr(c, "case_name", "案例")
        domain = getattr(c, "domain", "")
        app = getattr(c, "application", "")
        conf = getattr(c, "confidence_level", "初步")
        lines.append(f"• [{conf}] {name} ({domain}/{app})")
    return "\n".join(lines) if lines else "无相关仿真案例"


class SimulationEnricher:
    """
    Enrich QA answer sources with matching simulation cases and extracted rules.
    """

    async def _find_cases(
        self, db: AsyncSession, params: Dict[str, Any], limit: int = 3
    ) -> List[Any]:
        from ...db.simulation_models import SimulationCase
        stmt = select(SimulationCase)
        domain = params.get("domain")
        if domain:
            stmt = stmt.where(SimulationCase.domain == domain)
        stmt = stmt.limit(limit * 4)
        rows = (await db.execute(stmt)).scalars().all()

        # Score by keyword overlap in inputs
        def score(c: Any) -> int:
            inputs_str = str(c.inputs or {}).lower()
            return sum(1 for v in params.values() if str(v).lower() in inputs_str)

        return sorted(rows, key=score, reverse=True)[:limit]

    async def _find_rules(
        self, db: AsyncSession, params: Dict[str, Any], limit: int = 3
    ) -> List[Any]:
        from ...db.simulation_models import SimulationRule
        stmt = select(SimulationRule).order_by(
            SimulationRule.confidence.desc(), SimulationRule.applied_count.desc()
        ).limit(limit * 3)
        rows = (await db.execute(stmt)).scalars().all()

        # Filter by relevance: condition text contains any extracted param value
        matched = [
            r for r in rows
            if any(str(v).lower() in (r.condition or "").lower() for v in params.values())
            or not params  # if no params extracted, include top rules
        ]
        return matched[:limit] or rows[:limit]

    async def enrich_answer(
        self, db: AsyncSession, question: str, sources: List[Dict]
    ) -> List[Dict]:
        params = _extract_params(question)

        cases = await self._find_cases(db, params)
        if cases:
            sources.append({
                "type": "simulation_case",
                "content": _format_case_summary(cases),
                "source": "仿真案例库",
                "cases": [
                    {"id": c.id, "name": c.case_name, "confidence": c.confidence_level}
                    for c in cases
                ],
            })

        rules = await self._find_rules(db, params)
        if rules:
            sources.append({
                "type": "simulation_rule",
                "source": "仿真经验规则",
                "simulation_rules": [
                    {
                        "rule": r.title,
                        "condition": r.condition,
                        "recommendation": r.recommendation,
                        "confidence": r.confidence,
                        "source_cases": len(r.source_cases or []),
                    }
                    for r in rules
                ],
            })

        return sources


simulation_enricher = SimulationEnricher()
