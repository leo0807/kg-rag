"""
src/routers/graph_references.py
文档引用关系图专用接口
"""
import logging
from fastapi import APIRouter, Depends, Query
from neo4j import Driver
from ...core.database import get_driver

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["graph"])


@router.get("/graph/references")
async def get_references_graph(
    doc_id: str  = Query(default="", description="聚焦文档 ID，留空返回全局视图"),
    depth:  int  = Query(default=1, ge=1, le=2, description="扩散深度 1 或 2"),
    driver: Driver = Depends(get_driver),
):
    """
    文档引用关系图。
    - 不传 doc_id：返回全局引用网络（所有 Document 间 REFERENCES 边）
    - 传 doc_id：以该文档为中心，返回 depth 跳内的引用邻域
    """
    with driver.session() as session:
        if not doc_id:
            # ── 全局视图 ──────────────────────────────────────────────────────
            edge_result = session.run("""
                MATCH (a:Document)-[r:REFERENCES]->(b:Document)
                RETURN
                    a.name  AS source,
                    coalesce(a.title, a.name) AS source_title,
                    b.name  AS target,
                    coalesce(b.title, b.name) AS target_title
            """)
            raw_edges: list[dict] = [dict(e) for e in edge_result]

            # 聚合权重（同一 source→target 对可能多次出现）
            weight_map: dict[tuple, int] = {}
            for e in raw_edges:
                key = (e["source"], e["target"])
                weight_map[key] = weight_map.get(key, 0) + 1

            # 收集节点信息
            node_map: dict[str, dict] = {}
            for e in raw_edges:
                for nid, title in [(e["source"], e["source_title"]),
                                   (e["target"], e["target_title"])]:
                    if nid not in node_map:
                        node_map[nid] = {"id": nid, "title": title or nid,
                                         "ref_out_count": 0, "ref_in_count": 0,
                                         "is_center": False}
                node_map[e["source"]]["ref_out_count"] += 1
                node_map[e["target"]]["ref_in_count"]  += 1

            nodes = list(node_map.values())
            edges = [
                {"source": src, "target": tgt, "weight": w}
                for (src, tgt), w in weight_map.items()
            ]

        else:
            # ── 聚焦视图 ──────────────────────────────────────────────────────
            hop = "*1..2" if depth == 2 else ""

            result = session.run(f"""
                MATCH (center:Document {{name: $doc_id}})
                OPTIONAL MATCH (center)-[:REFERENCES{hop}]->(out:Document)
                OPTIONAL MATCH (in:Document)-[:REFERENCES{hop}]->(center)
                RETURN
                    center.name                              AS center_id,
                    coalesce(center.title, center.name)      AS center_title,
                    collect(DISTINCT {{
                        id:    out.name,
                        title: coalesce(out.title, out.name)
                    }})                                      AS out_docs,
                    collect(DISTINCT {{
                        id:    in.name,
                        title: coalesce(in.title, in.name)
                    }})                                      AS in_docs
            """, doc_id=doc_id)
            row = result.single()
            if not row:
                return {"nodes": [], "edges": [], "stats": {}}

            center_id    = row["center_id"]
            center_title = row["center_title"]
            out_docs     = [d for d in row["out_docs"] if d.get("id")]
            in_docs      = [d for d in row["in_docs"]  if d.get("id")]

            # 如果 depth=2，还需要把邻居的邻居之间的边也查出来
            all_ids = {center_id} | {d["id"] for d in out_docs} | {d["id"] for d in in_docs}

            edge_result = session.run("""
                MATCH (a:Document)-[r:REFERENCES]->(b:Document)
                WHERE a.name IN $ids AND b.name IN $ids
                RETURN a.name AS source, b.name AS target, count(r) AS weight
            """, ids=list(all_ids))
            edges = [{"source": e["source"], "target": e["target"], "weight": e["weight"]}
                     for e in edge_result]

            node_map: dict[str, dict] = {}
            for nid, title in [(center_id, center_title)] + \
                               [(d["id"], d["title"]) for d in out_docs + in_docs]:
                if nid not in node_map:
                    node_map[nid] = {"id": nid, "title": title or nid,
                                     "ref_out_count": 0, "ref_in_count": 0,
                                     "is_center": nid == center_id}
            for e in edges:
                if e["source"] in node_map:
                    node_map[e["source"]]["ref_out_count"] += e["weight"]
                if e["target"] in node_map:
                    node_map[e["target"]]["ref_in_count"] += e["weight"]

            nodes = list(node_map.values())

        # ── 统计摘要 ──────────────────────────────────────────────────────────
        most_cited = max(nodes, key=lambda n: n["ref_in_count"], default=None)
        stats = {
            "total_docs": len(nodes),
            "total_refs": sum(e["weight"] for e in edges),
            "most_cited": {
                "doc_id": most_cited["id"],
                "count":  most_cited["ref_in_count"],
            } if most_cited and most_cited["ref_in_count"] > 0 else None,
        }

    return {"nodes": nodes, "edges": edges, "stats": stats}
