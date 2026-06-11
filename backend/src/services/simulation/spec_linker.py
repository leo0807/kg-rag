"""K3.1: Auto-link simulation cases to knowledge-graph specs/sections."""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# ── Keyword sets per domain ────────────────────────────────────────────────────
_DOMAIN_KEYWORDS: Dict[str, List[str]] = {
    "structural": ["应力", "应变", "强度", "疲劳", "刚度", "载荷", "位移"],
    "thermal":    ["温度", "热", "导热", "散热", "热应力", "冷却"],
    "fluid":      ["流速", "压力", "流量", "湍流", "雷诺", "边界层"],
    "coupled":    ["热-力", "耦合", "多物理", "热固耦合"],
}

_PROCESS_KEYWORDS: Dict[str, List[str]] = {
    "密封":       ["密封", "seal", "防渗", "泄漏"],
    "装配":       ["装配", "配合", "间隙", "过盈"],
    "焊接":       ["焊接", "焊缝", "熔深", "热影响"],
    "复合材料成型": ["复合", "铺层", "固化", "纤维"],
}


class SpecLinker:
    """
    Auto-link simulation cases to spec nodes in the knowledge graph using
    keyword, application, and process matching strategies.
    """

    def __init__(self, similarity_threshold: float = 0.3) -> None:
        self.threshold = similarity_threshold

    # ── Strategy 1: parameter keyword match ───────────────────────────────────
    async def _match_by_params(self, case: Any) -> List[Dict]:
        domain = getattr(case, "domain", "")
        keywords = _DOMAIN_KEYWORDS.get(domain, [])
        inputs_str = str(case.inputs or {}).lower()
        score = sum(1 for kw in keywords if kw in inputs_str) / max(len(keywords), 1)
        if score >= self.threshold:
            return [{"match_type": "params", "score": score, "domain": domain}]
        return []

    # ── Strategy 2: application scene match ───────────────────────────────────
    async def _match_by_application(self, case: Any) -> List[Dict]:
        app = getattr(case, "application", "").lower()
        results: List[Dict] = []
        for scene, keywords in _PROCESS_KEYWORDS.items():
            if any(kw in app for kw in keywords):
                results.append({"match_type": "application", "scene": scene, "score": 0.7})
        return results

    # ── Strategy 3: process/material match ────────────────────────────────────
    async def _match_by_process(self, case: Any) -> List[Dict]:
        desc = (getattr(case, "description", "") or "").lower()
        inputs_str = str(case.inputs or {}).lower()
        text = desc + " " + inputs_str
        results: List[Dict] = []
        for scene, keywords in _PROCESS_KEYWORDS.items():
            hits = sum(1 for kw in keywords if kw in text)
            if hits >= 1:
                results.append({"match_type": "process", "scene": scene,
                                "score": min(hits / len(keywords), 1.0)})
        return results

    # ── Aggregate across strategies ───────────────────────────────────────────
    def _aggregate_matches(self, groups: List[List[Dict]]) -> List[Dict]:
        seen: Dict[str, Dict] = {}
        for group in groups:
            for m in group:
                key = m.get("scene") or m.get("domain") or "generic"
                if key not in seen or m["score"] > seen[key]["score"]:
                    seen[key] = m
        return sorted(seen.values(), key=lambda x: x["score"], reverse=True)

    # ── Create Neo4j relation ─────────────────────────────────────────────────
    async def _create_relation(self, case_id: str, match: Dict) -> None:
        try:
            from ..graph.connection import get_neo4j_driver
            async with get_neo4j_driver() as driver:
                async with driver.session() as sess:
                    await sess.run(
                        "MATCH (c:SimulationCase {id: $cid}) "
                        "MERGE (c)-[r:REFERENCES_SPEC {match_type: $mt}]->"
                        "(:SpecDomain {name: $domain}) "
                        "SET r.score = $score, r.updated = timestamp()",
                        cid=case_id, mt=match.get("match_type", "auto"),
                        domain=match.get("scene") or match.get("domain", ""),
                        score=match.get("score", 0.0),
                    )
        except Exception as e:
            logger.debug("Neo4j relation skipped: %s", e)

    async def auto_link(self, db: AsyncSession, case_id: str) -> List[Dict]:
        from ...db.simulation_models import SimulationCase
        case = await db.get(SimulationCase, case_id)
        if not case:
            return []

        param_matches   = await self._match_by_params(case)
        app_matches     = await self._match_by_application(case)
        process_matches = await self._match_by_process(case)

        candidates = self._aggregate_matches([param_matches, app_matches, process_matches])

        # Persist top-5 relations to Neo4j
        for candidate in candidates[:5]:
            await self._create_relation(case_id, candidate)

        # Also update related_specs in DB if matches found
        if candidates:
            new_specs = [c.get("scene") or c.get("domain") for c in candidates[:3] if c.get("scene") or c.get("domain")]
            existing = list(case.related_specs or [])
            for s in new_specs:
                if s and s not in existing:
                    existing.append(s)
            case.related_specs = existing
            await db.commit()

        return candidates


spec_linker = SpecLinker()
