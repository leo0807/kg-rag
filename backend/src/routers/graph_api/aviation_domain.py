"""
Aviation manufacturing domain extensions.

POST /api/admin/graph/airworthiness/map   — 适航条款 → 工艺章节映射
GET  /api/graph/airworthiness             — 按适航条款查询工艺依据
POST /api/admin/graph/fmea/import         — 导入 FMEA 失效模式数据
GET  /api/graph/fmea                      — 查询高风险工序（按 RPN 排序）
POST /api/admin/graph/special-process/register — 注册特种工艺节点
GET  /api/graph/special-processes         — 查询特种工艺认证要求
POST /api/admin/graph/fai/link            — 首件鉴定报告与章节挂钩
GET  /api/graph/fai?chunk_id=             — 查询工序首件鉴定状态
POST /api/admin/graph/eco/create          — 创建 ECO 变更节点
GET  /api/graph/eco/{eco_id}              — 查询 ECO 影响范围
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ...auth.deps import get_admin_user, get_current_user
from ...core.database import get_driver
from ...db.models import User

log = logging.getLogger(__name__)
router = APIRouter(tags=["aviation-domain"])

_AW_REGS = {"CCAR-25", "FAR-25", "CS-25", "CCAR-21", "AC-21"}


# ---------------------------------------------------------------------------
# Airworthiness compliance mapping
# ---------------------------------------------------------------------------

class AirworthinessMapBody(BaseModel):
    regulation:   str          # CCAR-25, FAR-25, CS-25
    clause_ref:   str          # e.g. "25.571"
    clause_title: str = ""
    chunk_ids:    list[str]


@router.post("/api/admin/graph/airworthiness/map")
async def map_airworthiness(
    body: AirworthinessMapBody,
    _: User = Depends(get_admin_user),
) -> dict[str, Any]:
    """Link airworthiness regulation clauses to process sections."""
    driver = get_driver()
    with driver.session() as s:
        s.run("""
            MERGE (aw:AirworthinessClause {regulation: $reg, clause_ref: $ref})
            SET aw.clause_title = $title
            WITH aw
            UNWIND $chunks AS cid
              MATCH (sec:Section {chunk_id: cid})
              MERGE (sec)-[:SATISFIES_AW]->(aw)
        """, reg=body.regulation, ref=body.clause_ref,
            title=body.clause_title, chunks=body.chunk_ids)
    return {"ok": True, "regulation": body.regulation,
            "clause": body.clause_ref, "mapped": len(body.chunk_ids)}


@router.get("/api/graph/airworthiness")
async def query_airworthiness(
    regulation: str = Query(..., description="如 CCAR-25"),
    clause_ref: str | None = Query(None),
    _: User = Depends(get_current_user),
) -> dict[str, Any]:
    driver = get_driver()
    with driver.session() as s:
        extra = "AND aw.clause_ref = $ref " if clause_ref else ""
        result = s.run(
            f"""
            MATCH (sec:Section)-[:SATISFIES_AW]->(aw:AirworthinessClause)
            WHERE aw.regulation = $reg {extra}
            RETURN aw.clause_ref AS clause_ref, aw.clause_title AS clause_title,
                   collect(sec.chunk_id) AS section_ids,
                   count(sec) AS section_count
            ORDER BY aw.clause_ref
            """,
            reg=regulation, **{"ref": clause_ref} if clause_ref else {},
        )
        rows = [dict(r) for r in result]
    return {"regulation": regulation, "clauses": rows}


# ---------------------------------------------------------------------------
# FMEA
# ---------------------------------------------------------------------------

class FMEAImportBody(BaseModel):
    entries: list[dict]  # [{process_id, failure_mode, severity, occurrence, detection, rpn}]


@router.post("/api/admin/graph/fmea/import")
async def import_fmea(
    body: FMEAImportBody,
    _: User = Depends(get_admin_user),
) -> dict[str, Any]:
    driver = get_driver()
    n = 0
    with driver.session() as s:
        for e in body.entries:
            s.run("""
                MERGE (fm:FailureMode {
                    process_id: $pid, failure_mode: $fm
                })
                SET fm.severity    = $sev,
                    fm.occurrence  = $occ,
                    fm.detection   = $det,
                    fm.rpn         = $rpn
                WITH fm
                MATCH (sec:Section {chunk_id: $pid})
                MERGE (sec)-[:HAS_FAILURE_MODE]->(fm)
            """, pid=e.get("process_id", ""), fm=e.get("failure_mode", ""),
                sev=e.get("severity", 0), occ=e.get("occurrence", 0),
                det=e.get("detection", 0), rpn=e.get("rpn", 0))
            n += 1
    return {"ok": True, "imported": n}


@router.get("/api/graph/fmea")
async def query_fmea(
    min_rpn: int = Query(100, description="最低 RPN 风险数"),
    limit:   int = Query(30, ge=1, le=200),
    _: User = Depends(get_current_user),
) -> dict[str, Any]:
    driver = get_driver()
    with driver.session() as s:
        result = s.run("""
            MATCH (sec:Section)-[:HAS_FAILURE_MODE]->(fm:FailureMode)
            WHERE fm.rpn >= $min_rpn
            RETURN sec.chunk_id AS chunk_id, sec.title AS title,
                   fm.failure_mode AS failure_mode, fm.rpn AS rpn,
                   fm.severity AS severity, fm.occurrence AS occurrence,
                   fm.detection AS detection
            ORDER BY fm.rpn DESC
            LIMIT $lim
        """, min_rpn=min_rpn, lim=limit)
        rows = [dict(r) for r in result]
    return {"min_rpn": min_rpn, "count": len(rows), "failures": rows}


# ---------------------------------------------------------------------------
# Special processes
# ---------------------------------------------------------------------------

class SpecialProcessBody(BaseModel):
    process_id:   str
    process_type: str   # welding | heat_treatment | surface_treatment | ndt
    certification_standard: str = ""
    operator_qualification:  str = ""
    equipment_cert_days:     int | None = None
    chunk_ids: list[str] = []


@router.post("/api/admin/graph/special-process/register")
async def register_special_process(
    body: SpecialProcessBody,
    _: User = Depends(get_admin_user),
) -> dict[str, Any]:
    driver = get_driver()
    with driver.session() as s:
        s.run("""
            MERGE (sp:SpecialProcess {process_id: $pid})
            SET sp.process_type  = $ptype,
                sp.certification_standard = $cert,
                sp.operator_qualification = $qual,
                sp.equipment_cert_days    = $days
            WITH sp
            UNWIND $chunks AS cid
              MATCH (sec:Section {chunk_id: cid})
              MERGE (sec)-[:INVOLVES_SPECIAL_PROCESS]->(sp)
        """, pid=body.process_id, ptype=body.process_type,
            cert=body.certification_standard, qual=body.operator_qualification,
            days=body.equipment_cert_days, chunks=body.chunk_ids)
    return {"ok": True, "process_id": body.process_id}


@router.get("/api/graph/special-processes")
async def list_special_processes(
    process_type: str | None = Query(None),
    _: User = Depends(get_current_user),
) -> dict[str, Any]:
    driver = get_driver()
    with driver.session() as s:
        extra = "WHERE sp.process_type = $pt " if process_type else ""
        result = s.run(
            f"MATCH (sp:SpecialProcess) {extra}"
            "RETURN sp.process_id AS id, sp.process_type AS type, "
            "sp.certification_standard AS cert, sp.operator_qualification AS qual "
            "ORDER BY sp.process_type LIMIT 100",
            **{"pt": process_type} if process_type else {},
        )
        return {"processes": [dict(r) for r in result]}


# ---------------------------------------------------------------------------
# FAI (First Article Inspection)
# ---------------------------------------------------------------------------

class FAILinkBody(BaseModel):
    fai_doc_id: str
    chunk_ids:  list[str]


@router.post("/api/admin/graph/fai/link")
async def link_fai(body: FAILinkBody, _: User = Depends(get_admin_user)) -> dict[str, Any]:
    driver = get_driver()
    with driver.session() as s:
        s.run("""
            MATCH (fai:Document {doc_id: $did})
            SET fai.type = 'FAI'
            WITH fai
            UNWIND $chunks AS cid
              MATCH (sec:Section {chunk_id: cid})
              MERGE (fai)-[:VALIDATES]->(sec)
        """, did=body.fai_doc_id, chunks=body.chunk_ids)
    return {"ok": True, "fai_doc_id": body.fai_doc_id, "linked": len(body.chunk_ids)}


@router.get("/api/graph/fai")
async def get_fai_status(
    chunk_id: str = Query(...),
    _: User = Depends(get_current_user),
) -> dict[str, Any]:
    driver = get_driver()
    with driver.session() as s:
        result = s.run("""
            MATCH (fai:Document {type: 'FAI'})-[:VALIDATES]->(sec:Section {chunk_id: $cid})
            RETURN fai.doc_id AS fai_doc_id, fai.title AS title, fai.version AS version
        """, cid=chunk_id)
        fais = [dict(r) for r in result]
    return {"chunk_id": chunk_id, "fai_count": len(fais), "fai_records": fais}


# ---------------------------------------------------------------------------
# ECO (Engineering Change Order)
# ---------------------------------------------------------------------------

class ECOBody(BaseModel):
    eco_id:      str
    description: str
    affected_component_pns: list[str] = []
    old_chunk_ids: list[str] = []
    new_chunk_ids: list[str] = []
    effective_date: str = ""


@router.post("/api/admin/graph/eco/create")
async def create_eco(body: ECOBody, _: User = Depends(get_admin_user)) -> dict[str, Any]:
    driver = get_driver()
    with driver.session() as s:
        s.run("""
            MERGE (eco:ECO {eco_id: $eid})
            SET eco.description = $desc, eco.effective_date = $date
        """, eid=body.eco_id, desc=body.description, date=body.effective_date)
        for pn in body.affected_component_pns:
            s.run("MATCH (c:Component {part_no: $pn}) "
                  "MATCH (eco:ECO {eco_id: $eid}) MERGE (eco)-[:AFFECTS]->(c)",
                  pn=pn, eid=body.eco_id)
        for cid in body.old_chunk_ids:
            s.run("MATCH (eco:ECO {eco_id: $eid}), (s:Section {chunk_id: $cid}) "
                  "MERGE (eco)-[:CHANGES_FROM]->(s)", eid=body.eco_id, cid=cid)
        for cid in body.new_chunk_ids:
            s.run("MATCH (eco:ECO {eco_id: $eid}), (s:Section {chunk_id: $cid}) "
                  "MERGE (eco)-[:CHANGES_TO]->(s)", eid=body.eco_id, cid=cid)
    return {"ok": True, "eco_id": body.eco_id}


@router.get("/api/graph/eco/{eco_id}")
async def get_eco(eco_id: str, _: User = Depends(get_current_user)) -> dict[str, Any]:
    driver = get_driver()
    with driver.session() as s:
        eco_r = s.run("MATCH (e:ECO {eco_id: $eid}) RETURN e.description AS desc, "
                      "e.effective_date AS date", eid=eco_id).single()
        if not eco_r:
            from fastapi import HTTPException  # noqa: PLC0415
            raise HTTPException(status_code=404, detail="ECO not found")
        comps_r = s.run("MATCH (e:ECO {eco_id: $eid})-[:AFFECTS]->(c:Component) "
                        "RETURN c.part_no AS pn", eid=eco_id)
        from_r = s.run("MATCH (e:ECO {eco_id: $eid})-[:CHANGES_FROM]->(s:Section) "
                       "RETURN s.chunk_id AS cid, s.title AS title", eid=eco_id)
        to_r   = s.run("MATCH (e:ECO {eco_id: $eid})-[:CHANGES_TO]->(s:Section) "
                       "RETURN s.chunk_id AS cid, s.title AS title", eid=eco_id)
    return {
        "eco_id": eco_id, "description": eco_r["desc"], "date": eco_r["date"],
        "affected_components": [r["pn"] for r in comps_r],
        "changes_from": [dict(r) for r in from_r],
        "changes_to":   [dict(r) for r in to_r],
    }
