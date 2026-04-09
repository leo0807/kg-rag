import logging

from fastapi import APIRouter, Depends, Query
from neo4j import Driver

from ..core.database import get_driver

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
    from ..routers.feedback import QueryFeedback
    from ..db.session import AsyncSessionLocal

    since = datetime.utcnow() - timedelta(days=days)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(QueryFeedback.sources, QueryFeedback.detail)
            .where(QueryFeedback.created_at >= since)
        )
        rows = result.all()

    cited:   dict[str, int] = {}
    clicked: dict[str, int] = {}

    for sources_json, detail in rows:
        try:
            for s in _json.loads(sources_json or "[]"):
                cid = s.get("chunk_id")
                if cid:
                    cited[cid] = cited.get(cid, 0) + 1
        except Exception:
            pass
        if detail and detail.startswith("clicked_source:"):
            cid = detail[len("clicked_source:"):]
            if cid:
                clicked[cid] = clicked.get(cid, 0) + 1

    all_ids = set(cited) | set(clicked)
    if not all_ids:
        return {"nodes": [], "max_heat": 0}

    heat = {cid: cited.get(cid, 0) + clicked.get(cid, 0) * 3.0 for cid in all_ids}
    max_heat = max(heat.values())
    ranked   = sorted(all_ids, key=lambda k: heat[k], reverse=True)[:top_k]

    return {
        "nodes": [
            {"chunk_id": cid, "heat_score": heat[cid], "heat_norm": round(heat[cid] / max_heat, 4)}
            for cid in ranked
        ],
        "max_heat": max_heat,
    }


@router.get("/graph")
async def get_graph(
    limit_doc:    int = 50,
    limit_sec:    int = 200,
    limit_img:    int = 100,
    limit_entity: int = 100,
    doc_id:       str = "",       # 按文档 doc_id 筛选
    driver: Driver = Depends(get_driver),
):
    with driver.session() as session:
        doc_filter = "WHERE $doc_id = '' OR d.name = $doc_id" if doc_id else ""

        # ── Document 节点 ─────────────────────────────────────────────────────
        doc_result = session.run(f"""
            MATCH (d:Document)
            {("WHERE $doc_id = '' OR d.name = $doc_id") if True else ""}
            RETURN d.name AS id, coalesce(d.title, d.name) AS name,
                   d.name AS doc_id, d.version AS version, 'Document' AS type
            LIMIT $limit
        """, doc_id=doc_id, limit=limit_doc)
        nodes = [
            {
                "id":      r["id"],
                "name":    r["name"],
                "doc_id":  r["doc_id"],
                "version": r["version"] or "",
                "type":    "Document",
            }
            for r in doc_result
        ]

        # ── Section 节点 ──────────────────────────────────────────────────────
        sec_result = session.run("""
            MATCH (s:Section)
            WHERE $doc_id = '' OR s.doc_id = $doc_id
            RETURN s.chunk_id AS id, s.title AS name, s.doc_id AS doc_id, 'Section' AS type
            LIMIT $limit
        """, doc_id=doc_id, limit=limit_sec)
        nodes += [
            {"id": r["id"], "name": r["name"] or r["id"], "type": "Section", "doc_id": r["doc_id"]}
            for r in sec_result
        ]

        # ── Image 节点 ────────────────────────────────────────────────────────
        img_result = session.run("""
            MATCH (i:Image)
            WHERE $doc_id = '' OR i.doc_id = $doc_id
            RETURN i.image_id AS id, i.caption AS name,
                   i.doc_id AS doc_id, i.description AS description, i.path AS path
            LIMIT $limit
        """, doc_id=doc_id, limit=limit_img)
        nodes += [
            {
                "id":          r["id"],
                "name":        r["name"] or r["id"],
                "type":        "Image",
                "doc_id":      r["doc_id"],
                "description": r["description"] or "",
                "path":        r["path"] or "",
            }
            for r in img_result
        ]

        # ── Tool 节点 ─────────────────────────────────────────────────────────
        tool_result = session.run("""
            MATCH (t:Tool)
            WHERE $doc_id = '' OR t.doc_id = $doc_id
            RETURN t.name AS id, t.name AS name, t.doc_id AS doc_id, 'Tool' AS type
            LIMIT $limit
        """, doc_id=doc_id, limit=limit_entity)
        nodes += [
            {"id": r["id"], "name": r["name"], "type": "Tool", "doc_id": r["doc_id"] or ""}
            for r in tool_result
        ]

        # ── Material 节点 ─────────────────────────────────────────────────────
        mat_result = session.run("""
            MATCH (m:Material)
            RETURN m.name AS id, m.name AS name, m.doc_id AS doc_id, 'Material' AS type
            LIMIT 100
        """)
        nodes += [
            {"id": r["id"], "name": r["name"], "type": "Material", "doc_id": r["doc_id"] or ""}
            for r in mat_result
        ]

        # ── Process 节点 ──────────────────────────────────────────────────────
        proc_result = session.run("""
            MATCH (p:Process)
            RETURN p.name AS id, p.name AS name, p.doc_id AS doc_id, 'Process' AS type
            LIMIT 100
        """)
        nodes += [
            {"id": r["id"], "name": r["name"], "type": "Process", "doc_id": r["doc_id"] or ""}
            for r in proc_result
        ]

        # ── Constraint 节点 ───────────────────────────────────────────────────
        con_result = session.run("""
            MATCH (c:Constraint)
            RETURN c.constraint_id AS id,
                   c.type + ': ' + c.value + c.unit AS name,
                   c.type AS con_type, c.value AS value, c.value_max AS value_max,
                   c.unit AS unit, c.description AS description,
                   c.standard AS standard, c.doc_id AS doc_id
            LIMIT 200
        """)
        nodes += [
            {
                "id":          r["id"],
                "name":        r["name"],
                "type":        "Constraint",
                "con_type":    r["con_type"],
                "value":       r["value"],
                "value_max":   r["value_max"] or "",
                "unit":        r["unit"],
                "description": r["description"] or "",
                "standard":    r["standard"] or "",
                "doc_id":      r["doc_id"] or "",
            }
            for r in con_result
        ]

        node_ids = {n["id"] for n in nodes}

        # ── 关系 ──────────────────────────────────────────────────────────────
        edges = []

        def _query_edges(cypher: str, **params):
            result = session.run(cypher, **params)
            return [
                dict(r) for r in result
                if r["source"] in node_ids and r["target"] in node_ids
            ]

        edges += _query_edges("""
            MATCH (d:Document)-[:HAS_SECTION]->(s:Section)
            RETURN d.name AS source, s.chunk_id AS target, 'HAS_SECTION' AS type
            LIMIT 300
        """)
        edges += _query_edges("""
            MATCH (d:Document)-[:REFERENCES]->(r:Document)
            RETURN d.name AS source, r.name AS target, 'REFERENCES' AS type
            LIMIT 100
        """)
        edges += _query_edges("""
            MATCH (s:Section)-[:HAS_SUBSECTION]->(c:Section)
            RETURN s.chunk_id AS source, c.chunk_id AS target, 'HAS_SUBSECTION' AS type
            LIMIT 300
        """)
        edges += _query_edges("""
            MATCH (s:Section)-[:HAS_IMAGE]->(i:Image)
            RETURN s.chunk_id AS source, i.image_id AS target, 'HAS_IMAGE' AS type
            LIMIT 200
        """)
        edges += _query_edges("""
            MATCH (s:Section)-[:REQUIRES_TOOL]->(t:Tool)
            RETURN s.chunk_id AS source, t.name AS target, 'REQUIRES_TOOL' AS type
            LIMIT 200
        """)
        edges += _query_edges("""
            MATCH (s:Section)-[:USES_MATERIAL]->(m:Material)
            RETURN s.chunk_id AS source, m.name AS target, 'USES_MATERIAL' AS type
            LIMIT 200
        """)
        edges += _query_edges("""
            MATCH (s:Section)-[:INVOLVES_PROCESS]->(p:Process)
            RETURN s.chunk_id AS source, p.name AS target, 'INVOLVES_PROCESS' AS type
            LIMIT 200
        """)
        edges += _query_edges("""
            MATCH (s:Section)-[:HAS_CONSTRAINT]->(c:Constraint)
            RETURN s.chunk_id AS source, c.constraint_id AS target, 'HAS_CONSTRAINT' AS type
            LIMIT 300
        """)
        edges += _query_edges("""
            MATCH (p:Process)-[:REQUIRES_TOOL]->(t:Tool)
            RETURN p.name AS source, t.name AS target, 'REQUIRES_TOOL' AS type
            LIMIT 100
        """)
        edges += _query_edges("""
            MATCH (p:Process)-[:USES_MATERIAL]->(m:Material)
            RETURN p.name AS source, m.name AS target, 'USES_MATERIAL' AS type
            LIMIT 100
        """)
        edges += _query_edges("""
            MATCH (a:Material)-[:ALTERNATIVE_TO]->(b:Material)
            RETURN a.name AS source, b.name AS target, 'ALTERNATIVE_TO' AS type
            LIMIT 100
        """)
        edges += _query_edges("""
            MATCH (a)-[:COMPATIBLE_WITH]->(b)
            RETURN elementId(a) AS source_eid, a.name AS source,
                   elementId(b) AS target_eid, b.name AS target, 'COMPATIBLE_WITH' AS type
            LIMIT 100
        """)
        edges += _query_edges("""
            MATCH (i:Image)-[:MENTIONS_TOOL]->(t:Tool)
            RETURN i.image_id AS source, t.name AS target, 'MENTIONS_TOOL' AS type
            LIMIT 100
        """)
        edges += _query_edges("""
            MATCH (new_doc:Document)-[:SUPERSEDES]->(old_doc:Document)
            RETURN new_doc.name AS source, old_doc.name AS target, 'SUPERSEDES' AS type
            LIMIT 50
        """)
        edges += _query_edges("""
            MATCH (a:Section)-[r:SIMILAR_TO]-(b:Section)
            WHERE a.chunk_id < b.chunk_id
            RETURN a.chunk_id AS source, b.chunk_id AS target,
                   'SIMILAR_TO' AS type
            LIMIT 100
        """)

    return {"nodes": nodes, "edges": edges}
