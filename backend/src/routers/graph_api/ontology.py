"""
Domain ontology and standards alignment.

GET  /api/graph/ata                       — ATA 100 章节码检索工艺规范
POST /api/admin/graph/ata/import          — 批量导入 ATA 映射
GET  /api/graph/compliance-matrix         — 规范 → 标准条款覆盖度矩阵
POST /api/admin/graph/compliance/map      — 新增规范-条款映射
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel

from ...auth.deps import get_admin_user, get_current_user
from ...core.database import get_driver
from ...db.models import User

log = logging.getLogger(__name__)
router = APIRouter(tags=["graph-ontology"])

# ---------------------------------------------------------------------------
# ATA 100 — top-level aerospace system classification
# ---------------------------------------------------------------------------

# Built-in ATA chapter seed (subset, easily extensible)
_ATA_CHAPTERS: dict[int, str] = {
    21: "空调", 22: "自动飞行", 23: "通信", 24: "电源",
    25: "设备和装饰", 26: "防火", 27: "飞行操纵", 28: "燃油",
    29: "液压", 30: "防冰排雨", 31: "仪表指示记录", 32: "起落架",
    33: "灯光", 34: "导航", 35: "氧气", 36: "引气", 38: "水/废物",
    45: "中央维护系统", 49: "机载辅助动力", 51: "结构",
    52: "门", 53: "机身", 54: "短舱", 55: "安定面",
    56: "窗", 57: "机翼", 71: "动力装置", 72: "发动机",
    73: "发动机燃油控制", 74: "点火", 75: "引气", 76: "发动机控制",
    77: "发动机指示", 78: "排气", 79: "发动机滑油", 80: "起动",
}


def _ensure_ata_nodes(chapters: dict[int, str]) -> None:
    driver = get_driver()
    with driver.session() as s:
        for chapter_no, name in chapters.items():
            s.run(
                "MERGE (a:ATAChapter {chapter_no: $no}) SET a.name = $name",
                no=chapter_no, name=name,
            )


def _query_ata(chapter_no: int, keyword: str | None) -> dict[str, Any]:
    driver = get_driver()
    with driver.session() as s:
        if chapter_no:
            result = s.run("""
                MATCH (a:ATAChapter {chapter_no: $no})<-[:BELONGS_TO_ATA]-(doc:Document)
                OPTIONAL MATCH (doc)-[:HAS_SECTION]->(sec:Section)
                RETURN doc.doc_id AS doc_id, doc.title AS title,
                       collect(sec.chunk_id)[..3] AS sample_chunks
                LIMIT 50
            """, no=chapter_no)
        else:
            result = s.run("""
                MATCH (a:ATAChapter)<-[:BELONGS_TO_ATA]-(doc:Document)
                RETURN a.chapter_no AS chapter_no, a.name AS chapter_name,
                       doc.doc_id AS doc_id, doc.title AS title
                LIMIT 100
            """)
        return {"results": [dict(r) for r in result]}


@router.get("/api/graph/ata")
async def query_ata(
    chapter: int | None = Query(None, description="ATA 章节号，如 29"),
    keyword: str | None = Query(None, description="系统名称关键字，如 液压"),
    _: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Return process specs mapped to an ATA 100 chapter.
    Initialises built-in ATA chapter nodes on first call.
    """
    await asyncio.to_thread(_ensure_ata_nodes, _ATA_CHAPTERS)
    if keyword and not chapter:
        # Find chapter_no by keyword
        matches = [no for no, name in _ATA_CHAPTERS.items() if keyword in name]
        chapter = matches[0] if matches else None

    if chapter and chapter not in _ATA_CHAPTERS:
        raise HTTPException(status_code=404, detail=f"ATA chapter {chapter} not in registry")

    data = await asyncio.to_thread(_query_ata, chapter or 0, keyword)
    return {
        "chapter":      chapter,
        "chapter_name": _ATA_CHAPTERS.get(chapter or 0),
        **data,
    }


class ATAMappingBody(BaseModel):
    mappings: list[dict]  # [{doc_id, chapter_no}]


@router.post("/api/admin/graph/ata/import")
async def import_ata_mappings(
    body: ATAMappingBody,
    _: User = Depends(get_admin_user),
) -> dict[str, Any]:
    """Bulk-link Document nodes to their ATA chapters."""
    await asyncio.to_thread(_ensure_ata_nodes, _ATA_CHAPTERS)
    driver = get_driver()
    linked = 0
    with driver.session() as s:
        for m in body.mappings:
            doc_id    = m.get("doc_id")
            chapter   = m.get("chapter_no")
            if not doc_id or not chapter:
                continue
            s.run("""
                MATCH (doc:Document {doc_id: $did})
                MERGE (a:ATAChapter {chapter_no: $no})
                  ON CREATE SET a.name = $name
                MERGE (doc)-[:BELONGS_TO_ATA]->(a)
            """, did=doc_id, no=chapter, name=_ATA_CHAPTERS.get(chapter, ""))
            linked += 1
    return {"ok": True, "linked": linked}


# ---------------------------------------------------------------------------
# Compliance matrix
# ---------------------------------------------------------------------------

def _compliance_matrix_query(standard: str | None) -> list[dict]:
    driver = get_driver()
    with driver.session() as s:
        if standard:
            result = s.run("""
                MATCH (std:Standard {name: $s})-[:HAS_CLAUSE]->(clause:Clause)
                OPTIONAL MATCH (clause)<-[:MAPS_TO]-(sec:Section)
                RETURN std.name AS standard,
                       clause.clause_id AS clause_id,
                       clause.text AS clause_text,
                       collect(sec.chunk_id) AS mapped_sections,
                       size(collect(sec.chunk_id)) AS coverage_count
                ORDER BY clause_id
            """, s=standard)
        else:
            result = s.run("""
                MATCH (std:Standard)
                OPTIONAL MATCH (std)-[:HAS_CLAUSE]->(clause:Clause)
                          <-[:MAPS_TO]-(sec:Section)
                RETURN std.name AS standard,
                       count(DISTINCT clause) AS total_clauses,
                       count(DISTINCT sec)    AS covered_sections
                ORDER BY std.name
            """)
        return [dict(r) for r in result]


@router.get("/api/graph/compliance-matrix")
async def compliance_matrix(
    standard: str | None = Query(None, description="标准名称，如 GJB241"),
    _: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Return coverage matrix: which Standard clauses are mapped to process sections.
    Gaps identify compliance blind spots.
    """
    rows = await asyncio.to_thread(_compliance_matrix_query, standard)
    gaps = [r for r in rows if isinstance(r.get("coverage_count"), int) and r["coverage_count"] == 0]
    return {
        "standard":    standard or "all",
        "total_rows":  len(rows),
        "gap_count":   len(gaps),
        "matrix":      rows,
    }


class ComplianceMappingBody(BaseModel):
    standard:   str
    clause_id:  str
    clause_text: str = ""
    chunk_ids:  list[str]  # Section nodes that satisfy this clause


@router.post("/api/admin/graph/compliance/map")
async def add_compliance_mapping(
    body: ComplianceMappingBody,
    _: User = Depends(get_admin_user),
) -> dict[str, Any]:
    """Link process sections to a standard clause."""
    driver = get_driver()
    with driver.session() as s:
        s.run("""
            MERGE (std:Standard {name: $std})
            MERGE (c:Clause {clause_id: $cid, standard: $std})
              ON CREATE SET c.text = $txt
            WITH c
            UNWIND $chunks AS cid
              MATCH (sec:Section {chunk_id: cid})
              MERGE (sec)-[:MAPS_TO]->(c)
        """, std=body.standard, cid=body.clause_id,
             txt=body.clause_text, chunks=body.chunk_ids)
    return {"ok": True, "standard": body.standard, "clause": body.clause_id,
            "mapped": len(body.chunk_ids)}
