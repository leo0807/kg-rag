"""
Graph schema management — write Standard/Person/Equipment/Inspection/ChangeRecord
nodes and DERIVED_FROM / VALIDATED_BY / SUPERSEDES_SECTION / PRECEDES relationships.

POST /api/admin/graph/nodes/standard    — 新增 Standard 节点
POST /api/admin/graph/nodes/person      — 新增 Person 节点并关联文档
POST /api/admin/graph/nodes/equipment   — 新增 Equipment 节点
POST /api/admin/graph/nodes/inspection  — 新增 Inspection 节点
POST /api/admin/graph/nodes/change-record — 新增 ChangeRecord 节点
POST /api/admin/graph/rels/derived-from
POST /api/admin/graph/rels/validated-by
POST /api/admin/graph/rels/supersedes-section
POST /api/admin/graph/rels/precedes
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ...auth.deps import get_admin_user
from ...db.models import User
from ...services.graph.extended_nodes import (
    link_derived_from,
    link_document_authored,
    link_section_requires_equipment,
    link_section_requires_inspection,
    link_steps_precedes,
    link_supersedes_section,
    link_validated_by,
    merge_equipment,
    merge_inspection,
    merge_person,
    merge_standard,
    write_change_record,
)
from ...core.database import get_driver

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/graph", tags=["admin-schema"])


def _wrap(fn, *args, **kwargs) -> dict[str, Any]:
    try:
        driver = get_driver()
        fn(driver, *args, **kwargs)
        return {"ok": True}
    except Exception as exc:
        log.error("schema_mgmt: %s", exc)
        return {"ok": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Node creation
# ---------------------------------------------------------------------------

class StandardBody(BaseModel):
    std_id: str
    name:   str
    org:    str = ""
    version: str = ""
    doc_ids: list[str] = []   # link Document COMPLIES_WITH


@router.post("/nodes/standard")
async def create_standard(body: StandardBody, _: User = Depends(get_admin_user)) -> dict:
    result = _wrap(merge_standard, body.std_id, body.name, body.org, body.version)
    if result["ok"] and body.doc_ids:
        driver = get_driver()
        with driver.session() as s:
            for did in body.doc_ids:
                s.run("""
                    MERGE (std:Standard {std_id: $sid})
                    WITH std
                    MATCH (doc:Document {doc_id: $did})
                    MERGE (doc)-[:COMPLIES_WITH]->(std)
                """, sid=body.std_id, did=did)
    return {**result, "std_id": body.std_id}


class PersonBody(BaseModel):
    person_id: str
    name:      str
    role:      str = "author"   # author | reviewer | approver
    doc_ids:   list[str] = []


@router.post("/nodes/person")
async def create_person(body: PersonBody, _: User = Depends(get_admin_user)) -> dict:
    result = _wrap(merge_person, body.person_id, body.name, body.role)
    if result["ok"]:
        driver = get_driver()
        with driver.session() as s:
            for did in body.doc_ids:
                try:
                    link_document_authored(driver, did, body.person_id, body.role)
                except Exception as exc:
                    log.warning("link person %s → doc %s: %s", body.person_id, did, exc)
    return {**result, "person_id": body.person_id}


class EquipmentBody(BaseModel):
    equip_id:   str
    name:       str
    spec:       str = ""
    calibration_period_days: int | None = None
    chunk_ids:  list[str] = []


@router.post("/nodes/equipment")
async def create_equipment(body: EquipmentBody, _: User = Depends(get_admin_user)) -> dict:
    result = _wrap(merge_equipment, body.equip_id, body.name, body.spec,
                   body.calibration_period_days)
    if result["ok"]:
        driver = get_driver()
        for cid in body.chunk_ids:
            try:
                link_section_requires_equipment(driver, cid, body.equip_id)
            except Exception as exc:
                log.warning("link equip %s → section %s: %s", body.equip_id, cid, exc)
    return {**result, "equip_id": body.equip_id}


class InspectionBody(BaseModel):
    insp_id:            str
    method:             str
    frequency:          str = ""
    acceptance_criteria: str = ""
    chunk_ids:          list[str] = []


@router.post("/nodes/inspection")
async def create_inspection(body: InspectionBody, _: User = Depends(get_admin_user)) -> dict:
    result = _wrap(merge_inspection, body.insp_id, body.method,
                   body.frequency, body.acceptance_criteria)
    if result["ok"]:
        driver = get_driver()
        for cid in body.chunk_ids:
            try:
                link_section_requires_inspection(driver, cid, body.insp_id)
            except Exception as exc:
                log.warning("link insp %s → section %s: %s", body.insp_id, cid, exc)
    return {**result, "insp_id": body.insp_id}


class ChangeRecordBody(BaseModel):
    doc_id:      str
    record_id:   str
    description: str
    change_type: str = "revision"
    effective_date: str = ""
    approver:    str = ""


@router.post("/nodes/change-record")
async def create_change_record(body: ChangeRecordBody, _: User = Depends(get_admin_user)) -> dict:
    result = _wrap(write_change_record, body.doc_id, body.record_id,
                   body.description, body.change_type, body.effective_date, body.approver)
    return {**result, "record_id": body.record_id}


# ---------------------------------------------------------------------------
# Relationship creation
# ---------------------------------------------------------------------------

class DerivedFromBody(BaseModel):
    derived_chunk_id: str
    source_chunk_id:  str
    rationale:        str = ""


@router.post("/rels/derived-from")
async def rel_derived_from(body: DerivedFromBody, _: User = Depends(get_admin_user)) -> dict:
    return _wrap(link_derived_from, body.derived_chunk_id, body.source_chunk_id, body.rationale)


class ValidatedByBody(BaseModel):
    constraint_chunk_id: str
    test_doc_id:         str


@router.post("/rels/validated-by")
async def rel_validated_by(body: ValidatedByBody, _: User = Depends(get_admin_user)) -> dict:
    return _wrap(link_validated_by, body.constraint_chunk_id, body.test_doc_id)


class SupersedesSectionBody(BaseModel):
    new_chunk_id: str
    old_chunk_id: str


@router.post("/rels/supersedes-section")
async def rel_supersedes_section(body: SupersedesSectionBody, _: User = Depends(get_admin_user)) -> dict:
    return _wrap(link_supersedes_section, body.new_chunk_id, body.old_chunk_id)


class PrecedesBody(BaseModel):
    step_a_id: str
    step_b_id: str


@router.post("/rels/precedes")
async def rel_precedes(body: PrecedesBody, _: User = Depends(get_admin_user)) -> dict:
    return _wrap(link_steps_precedes, body.step_a_id, body.step_b_id)
