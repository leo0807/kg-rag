"""
高级查询接口

GET /api/search/constraints      — 参数范围约束查询（从 Constraint 节点检索）
GET /api/graph/version-lineage/{doc_id}  — 文档版本溯源（SUPERSEDES 链路）
GET /api/search/cross-references  — 跨规范引用检索（哪些章节引用了指定规范）
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from neo4j import Driver

from ...core.database import get_driver

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["search"])

# ── 参数范围约束查询 ────────────────────────────────────────────────────────

_CONSTRAINT_RANGE_QUERY = """
MATCH (s:Section)-[:HAS_CONSTRAINT]->(c:Constraint)
WHERE ($c_type  = '' OR toLower(c.type)  CONTAINS toLower($c_type))
  AND ($unit    = '' OR toLower(c.unit)  CONTAINS toLower($unit))
  AND ($doc_id  = '' OR s.doc_id = $doc_id)
  AND c.value IS NOT NULL AND c.value <> ''
WITH s, c,
     toFloat(c.value)     AS val,
     toFloat(c.value_min) AS v_min,
     toFloat(c.value_max) AS v_max
WHERE ($min_val IS NULL OR coalesce(v_min, val) >= $min_val)
  AND ($max_val IS NULL OR coalesce(v_max, val) <= $max_val)
RETURN
    s.chunk_id   AS chunk_id,
    s.doc_id     AS doc_id,
    s.number     AS number,
    s.title      AS title,
    c.type       AS c_type,
    c.value      AS value,
    c.value_min  AS value_min,
    c.value_max  AS value_max,
    c.unit       AS unit,
    c.description AS description
ORDER BY s.doc_id, s.number
LIMIT $limit
"""


@router.get("/search/constraints")
async def constraint_range_search(
    type:    str           = Query(default="", description="约束类型，如 temperature/pressure"),
    min_val: Optional[float] = Query(default=None, description="最小值（包含）"),
    max_val: Optional[float] = Query(default=None, description="最大值（包含）"),
    unit:    str           = Query(default="", description="单位，如 °C / MPa"),
    doc_id:  str           = Query(default="", description="限定文档 ID，留空全局搜索"),
    limit:   int           = Query(default=50, ge=1, le=200),
    driver:  Driver        = Depends(get_driver),
):
    """
    按工艺参数类型和数值范围检索约束条件。

    示例：type=temperature&min_val=100&max_val=300&unit=°C
    """
    with driver.session() as session:
        result = session.run(
            _CONSTRAINT_RANGE_QUERY,
            c_type=type,
            unit=unit,
            doc_id=doc_id,
            min_val=min_val,
            max_val=max_val,
            limit=limit,
        )
        rows = [dict(r) for r in result]

    return {
        "query":   {"type": type, "min_val": min_val, "max_val": max_val, "unit": unit},
        "total":   len(rows),
        "results": rows,
    }


# ── 版本溯源 ────────────────────────────────────────────────────────────────

@router.get("/graph/version-lineage/{doc_id}")
async def version_lineage(
    doc_id: str,
    driver: Driver = Depends(get_driver),
):
    """返回文档版本溯源链（SUPERSEDES 关系链路，向上向下各 3 跳）。"""
    with driver.session() as session:
        rec = session.run(
            "MATCH (d:Document {name: $doc_id}) RETURN d.name AS id, d.title AS title, "
            "d.version AS version LIMIT 1",
            doc_id=doc_id,
        ).single()
        if not rec:
            raise HTTPException(404, f"文档不存在: {doc_id}")

        # 向上：更新的版本（本文档被谁 SUPERSEDES）
        newer = session.run(
            "MATCH (newer:Document)-[:SUPERSEDES*1..3]->(d:Document {name: $doc_id}) "
            "RETURN newer.name AS id, coalesce(newer.title, newer.name) AS title, "
            "newer.version AS version ORDER BY newer.version",
            doc_id=doc_id,
        )
        newer_docs = [dict(r) for r in newer]

        # 向下：被本文档取代的旧版本
        older = session.run(
            "MATCH (d:Document {name: $doc_id})-[:SUPERSEDES*1..3]->(older:Document) "
            "RETURN older.name AS id, coalesce(older.title, older.name) AS title, "
            "older.version AS version ORDER BY older.version DESC",
            doc_id=doc_id,
        )
        older_docs = [dict(r) for r in older]

    return {
        "doc_id":     doc_id,
        "title":      rec["title"],
        "version":    rec["version"],
        "newer_versions": newer_docs,
        "older_versions": older_docs,
    }


# ── 跨规范引用检索 ──────────────────────────────────────────────────────────

@router.get("/search/cross-references")
async def cross_reference_search(
    target_doc: str = Query(..., description="被引用文档 ID"),
    limit:      int = Query(default=30, ge=1, le=100),
    driver:     Driver = Depends(get_driver),
):
    """
    查找所有引用了指定规范的章节（通过 REFERENCES 边及文本匹配）。
    """
    with driver.session() as session:
        # 通过 REFERENCES 边：Document → Section 路径
        result = session.run(
            """
            MATCH (src:Document)-[:REFERENCES]->(tgt:Document {name: $target})
            MATCH (src)-[:HAS_SECTION]->(s:Section)
            WHERE s.chunk_text CONTAINS $target
            RETURN
                src.name   AS doc_id,
                coalesce(src.title, src.name) AS doc_title,
                s.chunk_id AS chunk_id,
                s.number   AS number,
                s.title    AS title
            ORDER BY src.name, s.number
            LIMIT $limit
            """,
            target=target_doc,
            limit=limit,
        )
        rows = [dict(r) for r in result]

    return {
        "target_doc": target_doc,
        "total":      len(rows),
        "results":    rows,
    }
