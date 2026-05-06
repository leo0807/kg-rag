"""
GET /api/graph/schema-stats — 图谱本体论结构统计

返回节点类型、关系类型及各自数量，供前端 Schema 可视化使用。
"""
from __future__ import annotations

import logging
from fastapi import APIRouter, Depends
from neo4j import Driver

from ...core.database import get_driver

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/graph", tags=["graph"])

# 节点类型展示颜色
_NODE_COLORS: dict[str, str] = {
    "Document":  "#1B4F9B",
    "Section":   "#5B8DB8",
    "Image":     "#2E7D32",
    "Table":     "#6A1B9A",
    "Tool":      "#E65100",
    "Material":  "#AD1457",
    "Process":   "#00695C",
    "Constraint":"#558B2F",
}

# 节点类型代表属性
_NODE_PROPERTIES: dict[str, list[str]] = {
    "Document":  ["doc_id", "title", "version", "issue_date", "doc_type"],
    "Section":   ["chunk_id", "number", "title", "level", "content"],
    "Image":     ["image_id", "doc_id", "page_index", "caption"],
    "Table":     ["table_id", "doc_id", "page_index", "headers"],
    "Tool":      ["name"],
    "Material":  ["name"],
    "Process":   ["name"],
    "Constraint":["name"],
}

# 关系类型说明
_REL_DESCRIPTIONS: dict[str, str] = {
    "HAS_SECTION":     "文档包含章节",
    "HAS_SUBSECTION":  "章节包含子章节",
    "NEXT_SECTION":    "章节顺序关系",
    "REFERENCES":      "文档引用文档",
    "HAS_IMAGE":       "章节含有图片",
    "HAS_TABLE":       "章节含有表格",
    "REQUIRES_TOOL":   "章节需要工具",
    "USES_MATERIAL":   "章节使用材料",
    "INVOLVES_PROCESS":"章节涉及工序",
    "HAS_CONSTRAINT":  "章节有约束条件",
    "SUPERSEDES":      "文档取代旧版",
    "SIMILAR_TO":      "章节相似",
}

NODE_LABELS = ["Document", "Section", "Image", "Table", "Tool", "Material", "Process", "Constraint"]
REL_TYPES = [
    ("HAS_SECTION", "Document", "Section"),
    ("HAS_SUBSECTION", "Section", "Section"),
    ("NEXT_SECTION", "Section", "Section"),
    ("REFERENCES", "Document", "Document"),
    ("HAS_IMAGE", "Section", "Image"),
    ("HAS_TABLE", "Section", "Table"),
    ("REQUIRES_TOOL", "Section", "Tool"),
    ("USES_MATERIAL", "Section", "Material"),
    ("INVOLVES_PROCESS", "Section", "Process"),
    ("HAS_CONSTRAINT", "Section", "Constraint"),
    ("SUPERSEDES", "Document", "Document"),
    ("SIMILAR_TO", "Section", "Section"),
]


@router.get("/schema-stats")
async def schema_stats(driver: Driver = Depends(get_driver)):
    with driver.session() as session:
        # Count each node label
        node_types = []
        sample_cache: dict[str, dict | None] = {}
        for label in NODE_LABELS:
            r = session.run(f"MATCH (n:{label}) RETURN count(n) AS cnt").single()
            cnt = r["cnt"] if r else 0

            sample = None
            if cnt > 0:
                try:
                    sr = session.run(
                        f"MATCH (n:{label}) RETURN properties(n) AS p LIMIT 1"
                    ).single()
                    if sr:
                        raw = dict(sr["p"])
                        # truncate long string values
                        sample = {k: (v[:80] if isinstance(v, str) else v)
                                  for k, v in raw.items()
                                  if not isinstance(v, (list, dict))}
                except Exception:
                    pass

            node_types.append({
                "type":       label,
                "count":      cnt,
                "color":      _NODE_COLORS.get(label, "#607D8B"),
                "properties": _NODE_PROPERTIES.get(label, []),
                "sample":     sample,
            })

        # Count each relationship type
        edge_types = []
        for rel, from_label, to_label in REL_TYPES:
            r = session.run(f"MATCH ()-[r:{rel}]->() RETURN count(r) AS cnt").single()
            cnt = r["cnt"] if r else 0
            edge_types.append({
                "type":        rel,
                "count":       cnt,
                "from":        from_label,
                "to":          to_label,
                "description": _REL_DESCRIPTIONS.get(rel, ""),
            })

    return {"node_types": node_types, "edge_types": edge_types}
