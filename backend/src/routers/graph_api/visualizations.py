"""
Graph visualization data APIs.

GET /api/graph/hierarchy           — Document → Section 层级树（树状图用）
GET /api/graph/adjacency-matrix    — 文档间 REFERENCES/SIMILAR_TO 关系矩阵
GET /api/graph/sankey              — Process → Tool → Material → Constraint 流量
GET /api/graph/geo-heatmap         — 车间工位工艺规范密度热力图
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, Depends, Query

from ...auth.deps import get_current_user
from ...core.database import get_driver
from ...db.models import User

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/graph", tags=["graph-viz"])


# ---------------------------------------------------------------------------
# Hierarchy tree
# ---------------------------------------------------------------------------

def _hierarchy_query(doc_id: str | None, depth: int) -> dict[str, Any]:
    driver = get_driver()
    with driver.session() as s:
        if doc_id:
            docs_result = s.run(
                "MATCH (d:Document {doc_id: $did}) RETURN d.doc_id AS id, d.title AS title",
                did=doc_id,
            )
        else:
            docs_result = s.run(
                "MATCH (d:Document) RETURN d.doc_id AS id, d.title AS title LIMIT 30"
            )
        docs = [dict(r) for r in docs_result]

        tree = []
        for doc in docs:
            sections_r = s.run(
                """
                MATCH (d:Document {doc_id: $did})-[:HAS_SECTION]->(sec:Section)
                RETURN sec.chunk_id AS id, sec.title AS title,
                       coalesce(sec.section_number, '') AS section_number,
                       sec.level AS level
                ORDER BY sec.chunk_id
                LIMIT 200
                """,
                did=doc["id"],
            )
            sections = [dict(r) for r in sections_r]
            tree.append({
                "id":       doc["id"],
                "name":     doc["title"] or doc["id"],
                "type":     "document",
                "children": [
                    {"id": s["id"], "name": s["title"] or s["id"],
                     "type": "section", "level": s.get("level")}
                    for s in sections
                ],
            })
    return {"nodes": len(docs), "tree": tree}


@router.get("/hierarchy")
async def hierarchy(
    doc_id: str | None = Query(None, description="Limit to a single document"),
    depth:  int = Query(2, ge=1, le=4),
    _: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Return Document → Section hierarchy suitable for a collapsible tree view."""
    return await asyncio.to_thread(_hierarchy_query, doc_id, depth)


# ---------------------------------------------------------------------------
# Adjacency matrix
# ---------------------------------------------------------------------------

def _adjacency_matrix_query(limit: int, rel_types: list[str]) -> dict[str, Any]:
    driver = get_driver()
    rel_filter = "|".join(rel_types) if rel_types else "REFERENCES|SIMILAR_TO"
    with driver.session() as s:
        docs_r = s.run(
            "MATCH (d:Document) RETURN d.doc_id AS id, d.title AS title LIMIT $lim",
            lim=limit,
        )
        docs  = [dict(r) for r in docs_r]
        ids   = [d["id"] for d in docs]
        index = {did: i for i, did in enumerate(ids)}
        n     = len(ids)
        matrix = [[0.0] * n for _ in range(n)]

        edges_r = s.run(
            f"""
            MATCH (a:Document)-[r:{rel_filter}]->(b:Document)
            WHERE a.doc_id IN $ids AND b.doc_id IN $ids
            RETURN a.doc_id AS src, b.doc_id AS tgt,
                   coalesce(r.similarity, 1.0) AS weight
            """,
            ids=ids,
        )
        for row in edges_r:
            i = index.get(row["src"])
            j = index.get(row["tgt"])
            if i is not None and j is not None:
                matrix[i][j] = float(row["weight"])

    return {
        "labels": [d.get("title") or d["id"] for d in docs],
        "ids":    ids,
        "matrix": matrix,
    }


@router.get("/adjacency-matrix")
async def adjacency_matrix(
    limit:     int  = Query(40, ge=2, le=100),
    rel_types: str  = Query("REFERENCES,SIMILAR_TO", description="Comma-separated rel types"),
    _: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Return document adjacency matrix for relationship heatmap visualization."""
    types = [t.strip() for t in rel_types.split(",") if t.strip()]
    return await asyncio.to_thread(_adjacency_matrix_query, limit, types)


# ---------------------------------------------------------------------------
# Sankey — process flow
# ---------------------------------------------------------------------------

def _sankey_query(doc_id: str | None) -> dict[str, Any]:
    driver = get_driver()
    with driver.session() as s:
        doc_filter = "AND s.doc_id = $did" if doc_id else ""
        params: dict = {}
        if doc_id:
            params["did"] = doc_id

        # Process → Tool
        pt = s.run(
            f"""
            MATCH (s:Section)-[:INVOLVES_PROCESS]->(p:Process)
            MATCH (s)-[:REQUIRES_TOOL]->(t:Tool)
            {doc_filter}
            RETURN p.name AS source, t.name AS target, count(*) AS value
            ORDER BY value DESC LIMIT 30
            """, **params,
        )
        # Tool → Material
        tm = s.run(
            f"""
            MATCH (s:Section)-[:REQUIRES_TOOL]->(t:Tool)
            MATCH (s)-[:USES_MATERIAL]->(m:Material)
            {doc_filter}
            RETURN t.name AS source, m.name AS target, count(*) AS value
            ORDER BY value DESC LIMIT 30
            """, **params,
        )
        # Material → Constraint
        mc = s.run(
            f"""
            MATCH (s:Section)-[:USES_MATERIAL]->(m:Material)
            MATCH (s)-[:HAS_CONSTRAINT]->(c:Constraint)
            {doc_filter}
            RETURN m.name AS source, c.parameter AS target, count(*) AS value
            ORDER BY value DESC LIMIT 20
            """, **params,
        )
        links = [dict(r) for r in pt] + [dict(r) for r in tm] + [dict(r) for r in mc]

        # Collect unique node names
        names: list[str] = []
        for link in links:
            if link["source"] not in names:
                names.append(link["source"])
            if link["target"] not in names:
                names.append(link["target"])

        node_index = {n: i for i, n in enumerate(names)}
        return {
            "nodes": [{"name": n} for n in names],
            "links": [
                {
                    "source": node_index[l["source"]],
                    "target": node_index[l["target"]],
                    "value":  l["value"],
                }
                for l in links
            ],
        }


@router.get("/sankey")
async def sankey(
    doc_id: str | None = Query(None),
    _: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Return process-tool-material-constraint flow data for Sankey diagram."""
    return await asyncio.to_thread(_sankey_query, doc_id)


# ---------------------------------------------------------------------------
# Geo heatmap — workshop density
# ---------------------------------------------------------------------------

def _geo_heatmap_query() -> list[dict]:
    driver = get_driver()
    with driver.session() as s:
        result = s.run("""
            MATCH (shop:Shop)-[:USES_SPEC]->(doc:Document)-[:HAS_SECTION]->(sec:Section)
            RETURN shop.shop_id AS shop_id, shop.name AS shop_name,
                   shop.location_x AS x, shop.location_y AS y,
                   count(sec) AS spec_count
            ORDER BY spec_count DESC
        """)
        return [dict(r) for r in result]


@router.get("/geo-heatmap")
async def geo_heatmap(
    _: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Return workshop-level spec density for factory floor heatmap overlay.
    Requires Shop nodes with location_x/location_y properties.
    """
    shops = await asyncio.to_thread(_geo_heatmap_query)
    return {"count": len(shops), "shops": shops}
