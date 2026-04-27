from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from neo4j import Driver

from ...auth.deps import get_admin_user
from ...core.database import get_driver
from ...db.models import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["graph"])

_CYPHER_DENY = ("delete", "detach", "drop", "create", "merge", "set", "remove",
                "call apoc", "call dbms", "load csv", "call db.index")


@router.get("/graph/schema")
async def get_graph_schema(driver: Driver = Depends(get_driver)):
    """获取图谱 Schema，包括所有标签和关系类型"""
    with driver.session() as session:
        labels_result = session.run("CALL db.labels()")
        labels = [r[0] for r in labels_result]
        rel_types_result = session.run("CALL db.relationshipTypes()")
        rel_types = [r[0] for r in rel_types_result]
        session.run("CALL db.schema.visualization()")
        return {"labels": labels, "relationship_types": rel_types}


@router.post("/graph/query")
async def execute_cypher_query(
    query: dict,
    driver: Driver = Depends(get_driver),
    _admin: User = Depends(get_admin_user),
):
    """执行自定义 Cypher 查询并返回图结果（仅管理员）"""
    cypher = query.get("cypher")
    if not cypher:
        return {"error": "Missing cypher query"}

    lowered = cypher.lower()
    if any(kw in lowered for kw in _CYPHER_DENY):
        return {"error": "不允许执行写入或危险操作", "success": False}

    with driver.session() as session:
        try:
            result = session.run(cypher)
            nodes = []
            edges = []
            node_ids = set()
            for record in result:
                for key in record.keys():
                    val = record[key]
                    if hasattr(val, "labels"):
                        try:
                            node_id = val.element_id
                        except AttributeError:
                            node_id = str(val.id)
                        if node_id not in node_ids:
                            node_ids.add(node_id)
                            nodes.append({
                                "id": node_id,
                                "labels": list(val.labels),
                                "properties": dict(val.items()),
                                "type": list(val.labels)[0] if val.labels else "Unknown",
                            })
                    elif hasattr(val, "type") and hasattr(val, "start_node"):
                        try:
                            rel_id = val.element_id
                            source_id = val.start_node.element_id
                            target_id = val.end_node.element_id
                        except AttributeError:
                            rel_id = str(val.id)
                            source_id = str(val.start_node.id)
                            target_id = str(val.end_node.id)
                        edges.append({
                            "id": rel_id, "source": source_id, "target": target_id,
                            "type": val.type, "properties": dict(val.items()),
                        })
            return {"nodes": nodes, "edges": edges, "success": True}
        except Exception as e:
            logger.error("Cypher execution failed: %s", e)
            return {"error": str(e), "success": False}
