"""
src/routers/graph_stats.py
知识图谱统计与时间线 API
"""
import logging
from fastapi import APIRouter, Depends
from neo4j import Driver
from ..core.database import get_driver

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["graph"])


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
