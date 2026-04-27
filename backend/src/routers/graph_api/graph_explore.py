from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from neo4j import Driver

from ...core.database import get_driver

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["graph"])


@router.get("/graph/hot-nodes")
async def graph_hot_nodes(days: int = 30, top_k: int = 200):
    """
    返回热点 Section 节点的归一化热力值，供图谱可视化使用（无需鉴权）。
    热力值 = cited_count + clicked_count × 3，归一化到 [0, 1]。
    """
    import json as _json
    from datetime import datetime, timedelta
    from sqlalchemy import select
    from ...routers.feedback import QueryFeedback
    from ...db.session import AsyncSessionLocal

    since = datetime.utcnow() - timedelta(days=days)
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(QueryFeedback.sources)
            .where(QueryFeedback.created_at >= since)
        )
        rows = result.all()

    cited: dict[str, int] = {}
    for (sources_json,) in rows:
        try:
            for s in _json.loads(sources_json or "[]"):
                cid = s.get("chunk_id")
                if cid:
                    cited[cid] = cited.get(cid, 0) + 1
        except Exception:
            pass

    all_ids = set(cited)
    if not all_ids:
        return {"nodes": [], "max_heat": 0}

    heat = {cid: float(cited[cid]) for cid in all_ids}
    max_heat = max(heat.values())
    ranked = sorted(all_ids, key=lambda k: heat[k], reverse=True)[:top_k]

    return {
        "nodes": [
            {"chunk_id": cid, "heat_score": heat[cid], "heat_norm": round(heat[cid] / max_heat, 4)}
            for cid in ranked
        ],
        "max_heat": max_heat,
    }


@router.get("/graph/expand/{chunk_id}")
async def expand_section(chunk_id: str, driver: Driver = Depends(get_driver)):
    """返回指定 Section 的直接子节点（用于前端按需展开）"""
    with driver.session() as session:
        result = session.run("""
            MATCH (parent:Section {chunk_id: $chunk_id})-[:HAS_SUBSECTION]->(child:Section)
            OPTIONAL MATCH (child)-[:HAS_SUBSECTION]->(grandchild:Section)
            WITH child, count(grandchild) AS grandchildren_count
            RETURN child.chunk_id AS id, child.title AS name, child.doc_id AS doc_id,
                   child.level AS level, child.number AS number,
                   grandchildren_count > 0 AS has_children, 'Section' AS type
        """, chunk_id=chunk_id)
        children = []
        for r in result:
            children.append({
                "id": r["id"], "name": r["name"] or r["id"], "type": "Section",
                "doc_id": r["doc_id"] or "", "level": r["level"] or 1,
                "number": r["number"] or "", "has_children": bool(r["has_children"]),
            })
    return {"nodes": children, "parent_id": chunk_id}
