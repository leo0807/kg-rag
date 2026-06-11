"""K4.1: Parametric case search with multi-criteria filtering and relevance ranking."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

_DOMAIN_CHOICES = {"structural", "thermal", "fluid", "coupled"}
_CONF_CHOICES   = {"已验证", "参考", "初步"}


class ParametricSearch:
    """
    Search simulation cases by physical parameters, domain, material,
    temperature/pressure ranges, and load type.
    """

    def _build_filters(self, criteria: Dict[str, Any]) -> list:
        from ...db.simulation_models import SimulationCase
        filters = []

        if domain := criteria.get("domain"):
            if domain in _DOMAIN_CHOICES:
                filters.append(SimulationCase.domain == domain)

        if app := criteria.get("application"):
            filters.append(SimulationCase.application.ilike(f"%{app}%"))

        if software := criteria.get("software"):
            filters.append(SimulationCase.software.ilike(f"%{software}%"))

        if conf := criteria.get("confidence_level"):
            if conf in _CONF_CHOICES:
                filters.append(SimulationCase.confidence_level == conf)

        if project := criteria.get("project_code"):
            filters.append(SimulationCase.project_code.ilike(f"%{project}%"))

        return filters

    def _rank(self, cases: List[Any], criteria: Dict[str, Any]) -> List[Any]:
        """Score by keyword overlap in inputs/description."""
        keywords = [
            str(criteria.get("material", "")),
            str(criteria.get("load_type", "")),
        ]
        keywords = [k for k in keywords if k]

        def score(c: Any) -> float:
            text = str(c.inputs or {}).lower() + " " + (c.description or "").lower()
            hits = sum(1 for kw in keywords if kw.lower() in text)
            # Bonus for verified confidence
            bonus = 0.3 if c.confidence_level == "已验证" else 0.1 if c.confidence_level == "参考" else 0.0
            return hits + bonus

        return sorted(cases, key=score, reverse=True)

    def _apply_range_filter(
        self, cases: List[Any], criteria: Dict[str, Any]
    ) -> List[Any]:
        """Post-filter by numeric ranges (temperature, pressure) in inputs dict."""
        t_range = criteria.get("temperature_range")
        p_range = criteria.get("pressure_range")

        if not t_range and not p_range:
            return cases

        filtered = []
        for c in cases:
            inputs = c.inputs or {}
            ok = True
            if t_range:
                temp = inputs.get("temperature") or inputs.get("温度")
                if temp is not None:
                    try:
                        v = float(temp)
                        if not (t_range[0] <= v <= t_range[1]):
                            ok = False
                    except (TypeError, ValueError):
                        pass
            if p_range and ok:
                pres = inputs.get("pressure") or inputs.get("压力")
                if pres is not None:
                    try:
                        v = float(pres)
                        if not (p_range[0] <= v <= p_range[1]):
                            ok = False
                    except (TypeError, ValueError):
                        pass
            if ok:
                filtered.append(c)
        return filtered

    async def search(
        self,
        db: AsyncSession,
        criteria: Dict[str, Any],
        skip: int = 0,
        limit: int = 30,
    ) -> List[Dict]:
        from ...db.simulation_models import SimulationCase

        # Build DB-level filters
        filters = self._build_filters(criteria)
        stmt = select(SimulationCase)
        if filters:
            stmt = stmt.where(and_(*filters))
        # Fetch a larger pool for in-memory range/rank
        stmt = stmt.offset(skip).limit(limit * 4)
        rows = (await db.execute(stmt)).scalars().all()

        # Python-side filters and ranking
        rows = self._apply_range_filter(list(rows), criteria)
        rows = self._rank(rows, criteria)
        rows = rows[:limit]

        return [
            {
                "id": c.id, "case_name": c.case_name, "case_code": c.case_code,
                "domain": c.domain, "application": c.application,
                "software": c.software, "confidence_level": c.confidence_level,
                "related_specs": c.related_specs,
                "inputs_summary": {k: v for k, v in list((c.inputs or {}).items())[:6]},
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in rows
        ]

    async def suggest_gaps(
        self, db: AsyncSession, domain: Optional[str] = None
    ) -> Dict[str, Any]:
        """Identify parameter regions with few existing cases."""
        from ...db.simulation_models import SimulationCase
        stmt = select(SimulationCase)
        if domain:
            stmt = stmt.where(SimulationCase.domain == domain)
        stmt = stmt.limit(500)
        rows = (await db.execute(stmt)).scalars().all()

        domain_counts: Dict[str, int] = {}
        app_counts: Dict[str, int] = {}
        for c in rows:
            domain_counts[c.domain] = domain_counts.get(c.domain, 0) + 1
            if c.application:
                app_counts[c.application] = app_counts.get(c.application, 0) + 1

        all_domains = ["structural", "thermal", "fluid", "coupled"]
        missing = [d for d in all_domains if domain_counts.get(d, 0) == 0]
        sparse  = [d for d in all_domains if 0 < domain_counts.get(d, 0) < 3]

        return {
            "total": len(rows),
            "domain_distribution": domain_counts,
            "application_distribution": dict(sorted(app_counts.items(), key=lambda x: -x[1])[:10]),
            "missing_domains": missing,
            "sparse_domains": sparse,
        }


parametric_search = ParametricSearch()
