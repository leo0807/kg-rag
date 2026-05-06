"""Node importance based on in-degree (simplified PageRank)."""
from __future__ import annotations
import asyncio
import logging
from fastapi import APIRouter, Depends
from neo4j import Driver
from ...core.database import get_driver

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/graph", tags=["graph"])


@router.get("/importance")
async def get_node_importance(driver: Driver = Depends(get_driver)):
    """Returns in-degree based importance scores (0–1) for graph nodes."""
    def _run():
        with driver.session() as s:
            rows = s.run("""
                MATCH (n) WHERE n:Document OR n:Section
                OPTIONAL MATCH (m)-[]->(n)
                WITH n, count(m) AS in_deg
                WHERE in_deg > 0
                RETURN
                    coalesce(n.chunk_id, n.doc_id, toString(id(n))) AS node_id,
                    labels(n)[0] AS node_type,
                    in_deg
                ORDER BY in_deg DESC
                LIMIT 500
            """)
            return [(r["node_id"], r["node_type"], r["in_deg"]) for r in rows]

    data = await asyncio.to_thread(_run)
    if not data:
        return {"nodes": []}
    max_deg = max(r[2] for r in data)
    return {
        "nodes": [
            {
                "id":          r[0],
                "type":        r[1],
                "in_degree":   r[2],
                "importance":  round(r[2] / max_deg, 3),
            }
            for r in data
        ]
    }
