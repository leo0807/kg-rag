import logging
from fastapi import APIRouter, Depends
from neo4j import Driver
from ..core.database import get_driver

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["graph"])


@router.get("/graph")
async def get_graph(driver: Driver = Depends(get_driver)):
    with driver.session() as session:

        # ── Document 节点 ─────────────────────
        doc_result = session.run("""
            MATCH (d:Document)
            RETURN d.name AS id,
                coalesce(d.title, d.name) AS name,
                d.name AS doc_id,
                'Document' AS type
            LIMIT 50
        """)
        nodes = [
            {
                "id":     r["id"],
                "name":   r["name"],
                "doc_id": r["doc_id"],  # 始终是 CPS 编号
                "type":   "Document",
            }
            for r in doc_result
        ]
        # ── Section 节点 ──────────────────────
        sec_result = session.run("""
            MATCH (s:Section)
            RETURN s.chunk_id AS id, s.title AS name, s.doc_id AS doc_id, 'Section' AS type
            LIMIT 200
        """)
        nodes += [{"id": r["id"], "name": r["name"] or r["id"], "type": "Section", "doc_id": r["doc_id"]} for r in sec_result]

        # ── Image 节点 ────────────────────────
        img_result = session.run("""
            MATCH (i:Image)
            RETURN i.image_id AS id, i.caption AS name,
                   i.doc_id AS doc_id, i.description AS description
            LIMIT 100
        """)
        nodes += [
            {
                "id":          r["id"],
                "name":        r["name"] or r["id"],
                "type":        "Image",
                "doc_id":      r["doc_id"],
                "description": r["description"] or "",
            }
            for r in img_result
        ]

        node_ids = {n["id"] for n in nodes}

        # ── HAS_SECTION 关系 ──────────────────
        edges = []
        hs_result = session.run("""
            MATCH (d:Document)-[:HAS_SECTION]->(s:Section)
            RETURN d.name AS source, s.chunk_id AS target, 'HAS_SECTION' AS type
            LIMIT 300
        """)
        edges += [dict(r) for r in hs_result if r["source"] in node_ids and r["target"] in node_ids]

        # ── REFERENCES 关系 ───────────────────
        ref_result = session.run("""
            MATCH (d:Document)-[:REFERENCES]->(r:Document)
            RETURN d.name AS source, r.name AS target, 'REFERENCES' AS type
            LIMIT 100
        """)
        edges += [dict(r) for r in ref_result if r["source"] in node_ids and r["target"] in node_ids]

        # ── HAS_SUBSECTION 关系 ───────────────
        sub_result = session.run("""
            MATCH (s:Section)-[:HAS_SUBSECTION]->(c:Section)
            RETURN s.chunk_id AS source, c.chunk_id AS target, 'HAS_SUBSECTION' AS type
            LIMIT 300
        """)
        edges += [dict(r) for r in sub_result if r["source"] in node_ids and r["target"] in node_ids]

        # ── HAS_IMAGE 关系 ────────────────────
        img_edge_result = session.run("""
            MATCH (s:Section)-[:HAS_IMAGE]->(i:Image)
            RETURN s.chunk_id AS source, i.image_id AS target, 'HAS_IMAGE' AS type
            LIMIT 200
        """)
        edges += [dict(r) for r in img_edge_result if r["source"] in node_ids and r["target"] in node_ids]

    return {"nodes": nodes, "edges": edges}