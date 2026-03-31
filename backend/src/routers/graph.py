import logging
from fastapi import APIRouter, Depends
from neo4j import Driver
from ..core.database import get_driver

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["graph"])


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


@router.get("/stats/knowledge-graph")
async def knowledge_graph_stats(driver: Driver = Depends(get_driver)):
    """
    返回知识图谱统计信息：各类节点数量、关系数量、覆盖率。
    """
    with driver.session() as session:

        # 节点计数
        node_counts = {}
        for label in ["Document", "Section", "Image", "Tool", "Material", "Process", "Constraint"]:
            r = session.run(f"MATCH (n:{label}) RETURN count(n) AS cnt").single()
            node_counts[label] = r["cnt"] if r else 0

        # 关系计数
        rel_counts = {}
        for rel in [
            "HAS_SECTION", "HAS_SUBSECTION", "NEXT_SECTION", "REFERENCES",
            "HAS_IMAGE", "REQUIRES_TOOL", "USES_MATERIAL", "INVOLVES_PROCESS",
            "HAS_CONSTRAINT", "ALTERNATIVE_TO", "COMPATIBLE_WITH",
            "MENTIONS_TOOL", "SUPERSEDES", "OBSOLETED_BY",
            "ADDED_SECTION", "REMOVED_SECTION", "CHANGED_TO", "SIMILAR_TO",
        ]:
            r = session.run(f"MATCH ()-[r:{rel}]->() RETURN count(r) AS cnt").single()
            rel_counts[rel] = r["cnt"] if r else 0

        # 覆盖率
        total_sections = node_counts["Section"] or 1
        r_tool = session.run("""
            MATCH (s:Section)-[:REQUIRES_TOOL]->(:Tool)
            RETURN count(DISTINCT s) AS cnt
        """).single()
        r_mat = session.run("""
            MATCH (s:Section)-[:USES_MATERIAL]->(:Material)
            RETURN count(DISTINCT s) AS cnt
        """).single()
        r_proc = session.run("""
            MATCH (s:Section)-[:INVOLVES_PROCESS]->(:Process)
            RETURN count(DISTINCT s) AS cnt
        """).single()
        r_con = session.run("""
            MATCH (s:Section)-[:HAS_CONSTRAINT]->(:Constraint)
            RETURN count(DISTINCT s) AS cnt
        """).single()
        r_img = session.run("""
            MATCH (s:Section)-[:HAS_IMAGE]->(:Image)
            RETURN count(DISTINCT s) AS cnt
        """).single()
        r_sim = session.run("""
            MATCH (s:Section)-[:SIMILAR_TO]-()
            RETURN count(DISTINCT s) AS cnt
        """).single()

        coverage = {
            "sections_with_tool":       round((r_tool["cnt"]  if r_tool  else 0) / total_sections * 100, 1),
            "sections_with_material":   round((r_mat["cnt"]   if r_mat   else 0) / total_sections * 100, 1),
            "sections_with_process":    round((r_proc["cnt"]  if r_proc  else 0) / total_sections * 100, 1),
            "sections_with_constraint": round((r_con["cnt"]   if r_con   else 0) / total_sections * 100, 1),
            "sections_with_image":      round((r_img["cnt"]   if r_img   else 0) / total_sections * 100, 1),
            "sections_with_similar":    round((r_sim["cnt"]   if r_sim   else 0) / total_sections * 100, 1),
        }

    return {
        "nodes":    node_counts,
        "relations": rel_counts,
        "coverage": coverage,
        "total_nodes": sum(node_counts.values()),
        "total_relations": sum(rel_counts.values()),
    }


@router.get("/graph/timeline")
async def get_timeline(driver: Driver = Depends(get_driver)):
    """
    版本时间线数据：返回所有文档的版本信息与章节变更统计。
    X 轴 = 版本号（字母序），Y 轴 = 文档基名，气泡大小 = 变更量。
    """
    with driver.session() as session:
        # ① 所有已入库文档（有 title 的才算正式文档）
        docs_res = session.run("""
            MATCH (d:Document)
            WHERE d.title IS NOT NULL
            RETURN d.name        AS doc_id,
                   d.title       AS title,
                   COALESCE(d.version, '')    AS version,
                   COALESCE(d.issue_date, '') AS issue_date
            ORDER BY d.name
        """)
        docs: dict[str, dict] = {}
        for r in docs_res:
            docs[r["doc_id"]] = {
                "doc_id":           r["doc_id"],
                "title":            r["title"],
                "version":          r["version"],
                "issue_date":       r["issue_date"],
                "supersedes":       [],
                "added_sections":   0,
                "removed_sections": 0,
                "changed_sections": 0,
            }

        # ② 版本溯源关系 SUPERSEDES
        sup_res = session.run("""
            MATCH (new:Document)-[:SUPERSEDES]->(old:Document)
            RETURN new.name AS new_id, old.name AS old_id
        """)
        for r in sup_res:
            if r["new_id"] in docs:
                docs[r["new_id"]]["supersedes"].append(r["old_id"])

        # ③ 新增章节计数（ADDED_SECTION）
        added_res = session.run("""
            MATCH (d:Document)-[:ADDED_SECTION]->()
            RETURN d.name AS doc_id, count(*) AS cnt
        """)
        for r in added_res:
            if r["doc_id"] in docs:
                docs[r["doc_id"]]["added_sections"] = r["cnt"]

        # ④ 删除章节计数（REMOVED_SECTION）
        removed_res = session.run("""
            MATCH (d:Document)-[:REMOVED_SECTION]->()
            RETURN d.name AS doc_id, count(*) AS cnt
        """)
        for r in removed_res:
            if r["doc_id"] in docs:
                docs[r["doc_id"]]["removed_sections"] = r["cnt"]

        # ⑤ 内容变更章节计数（CHANGED_TO）
        changed_res = session.run("""
            MATCH (d:Document)-[:HAS_SECTION]->(s:Section)-[:CHANGED_TO]->()
            RETURN d.name AS doc_id, count(s) AS cnt
        """)
        for r in changed_res:
            if r["doc_id"] in docs:
                docs[r["doc_id"]]["changed_sections"] = r["cnt"]

    return {"docs": list(docs.values())}


@router.post("/graph/semantic-links")
async def trigger_semantic_links(
    threshold: float = 0.88,
    top_k: int = 5,
    dry_run: bool = False,
    driver: Driver = Depends(get_driver),
):
    """
    触发跨文档语义边构建（离线批处理）。
    可先用 dry_run=true 预览会写入多少条边。
    """
    from ..services.semantic_linker import build_semantic_links
    result = build_semantic_links(driver, threshold=threshold, top_k=top_k, dry_run=dry_run)
    return result
