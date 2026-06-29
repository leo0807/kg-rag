"""
src/routers/graph_stats.py
知识图谱统计与时间线 API
"""
import logging
from fastapi import APIRouter, Depends
from neo4j import Driver
from ...core.database import get_driver

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["graph"])

_NODE_LABELS = ["Document", "Section", "Image", "Tool", "Material", "Process", "Constraint"]
_REL_TYPES   = [
    "HAS_SECTION", "HAS_SUBSECTION", "NEXT_SECTION", "REFERENCES",
    "HAS_IMAGE", "REQUIRES_TOOL", "USES_MATERIAL", "INVOLVES_PROCESS",
    "HAS_CONSTRAINT", "ALTERNATIVE_TO", "COMPATIBLE_WITH",
    "MENTIONS_TOOL", "SUPERSEDES", "OBSOLETED_BY",
    "ADDED_SECTION", "REMOVED_SECTION", "CHANGED_TO", "SIMILAR_TO",
]


@router.get("/stats/knowledge-graph")
async def knowledge_graph_stats(driver: Driver = Depends(get_driver)):
    """
    返回知识图谱统计信息：各类节点数量、关系数量、覆盖率。
    原 31 次串行 session.run() 合并为 3 次，减少约 28 次网络往返。
    """
    with driver.session() as session:

        # ── 查询 1：各标签节点计数（1 次代替 7 次循环）──────────────────────
        node_counts = {label: 0 for label in _NODE_LABELS}
        label_filter = " OR ".join(f"n:{lbl}" for lbl in _NODE_LABELS)
        for row in session.run(
            f"MATCH (n) WHERE {label_filter} RETURN labels(n)[0] AS lbl, count(n) AS cnt"
        ):
            if row["lbl"] in node_counts:
                node_counts[row["lbl"]] = row["cnt"]

        # ── 查询 2：各关系类型计数（1 次代替 18 次循环）────────────────────
        rel_counts = {r: 0 for r in _REL_TYPES}
        for row in session.run(
            "MATCH ()-[r]->() WHERE type(r) IN $rels RETURN type(r) AS rel, count(r) AS cnt",
            rels=_REL_TYPES,
        ):
            rel_counts[row["rel"]] = row["cnt"]

        # ── 查询 3：覆盖率（1 次 UNION ALL 代替 6 次单独查询）───────────────
        total_sections = node_counts["Section"] or 1
        cov_raw: dict[str, int] = {}
        for row in session.run("""
            MATCH (s:Section)-[:REQUIRES_TOOL]->(:Tool)    RETURN 'tool'       AS k, count(DISTINCT s) AS cnt
            UNION ALL
            MATCH (s:Section)-[:USES_MATERIAL]->(:Material) RETURN 'material'  AS k, count(DISTINCT s) AS cnt
            UNION ALL
            MATCH (s:Section)-[:INVOLVES_PROCESS]->(:Process) RETURN 'process' AS k, count(DISTINCT s) AS cnt
            UNION ALL
            MATCH (s:Section)-[:HAS_CONSTRAINT]->(:Constraint) RETURN 'constraint' AS k, count(DISTINCT s) AS cnt
            UNION ALL
            MATCH (s:Section)-[:HAS_IMAGE]->(:Image)        RETURN 'image'     AS k, count(DISTINCT s) AS cnt
            UNION ALL
            MATCH (s:Section)-[:SIMILAR_TO]-()              RETURN 'similar'   AS k, count(DISTINCT s) AS cnt
        """):
            cov_raw[row["k"]] = row["cnt"]

        coverage = {
            "sections_with_tool":       round(cov_raw.get("tool",       0) / total_sections * 100, 1),
            "sections_with_material":   round(cov_raw.get("material",   0) / total_sections * 100, 1),
            "sections_with_process":    round(cov_raw.get("process",    0) / total_sections * 100, 1),
            "sections_with_constraint": round(cov_raw.get("constraint", 0) / total_sections * 100, 1),
            "sections_with_image":      round(cov_raw.get("image",      0) / total_sections * 100, 1),
            "sections_with_similar":    round(cov_raw.get("similar",    0) / total_sections * 100, 1),
        }

    return {
        "nodes":         node_counts,
        "relations":     rel_counts,
        "coverage":      coverage,
        "total_nodes":   sum(node_counts.values()),
        "total_relations": sum(rel_counts.values()),
    }


@router.get("/graph/timeline")
async def get_timeline(driver: Driver = Depends(get_driver)):
    """
    版本时间线数据：返回所有文档的版本信息与章节变更统计。
    原 5 次串行查询合并为 2 次，减少 3 次网络往返。
    """
    with driver.session() as session:
        # ── 查询 1：文档基本信息 + SUPERSEDES 关系（1 次代替 2 次）──────────
        docs: dict[str, dict] = {}
        for r in session.run("""
            MATCH (d:Document)
            WHERE d.title IS NOT NULL
            OPTIONAL MATCH (d)-[:SUPERSEDES]->(old:Document)
            RETURN d.name AS doc_id,
                   d.title AS title,
                   coalesce(d.version, '')    AS version,
                   coalesce(d.issue_date, '') AS issue_date,
                   collect(old.name) AS supersedes
            ORDER BY d.name
        """):
            docs[r["doc_id"]] = {
                "doc_id":           r["doc_id"],
                "title":            r["title"],
                "version":          r["version"],
                "issue_date":       r["issue_date"],
                "supersedes":       [s for s in r["supersedes"] if s],
                "added_sections":   0,
                "removed_sections": 0,
                "changed_sections": 0,
            }

        # ── 查询 2：变更计数（1 次 UNION ALL 代替 3 次）────────────────────
        for r in session.run("""
            MATCH (d:Document)-[:ADDED_SECTION]->()
            RETURN d.name AS doc_id, 'added' AS kind, count(*) AS cnt
            UNION ALL
            MATCH (d:Document)-[:REMOVED_SECTION]->()
            RETURN d.name AS doc_id, 'removed' AS kind, count(*) AS cnt
            UNION ALL
            MATCH (d:Document)-[:HAS_SECTION]->(s:Section)-[:CHANGED_TO]->()
            RETURN d.name AS doc_id, 'changed' AS kind, count(s) AS cnt
        """):
            doc = docs.get(r["doc_id"])
            if not doc:
                continue
            if r["kind"] == "added":
                doc["added_sections"]   = r["cnt"]
            elif r["kind"] == "removed":
                doc["removed_sections"] = r["cnt"]
            else:
                doc["changed_sections"] = r["cnt"]

    return {"docs": list(docs.values())}
