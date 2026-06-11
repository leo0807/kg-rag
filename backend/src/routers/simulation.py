"""K2.1: Simulation case management API."""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import get_current_user
from ..db.models import User
from ..db.simulation_models import SimulationCase, SimulationParameter, SimulationResult
from ..db.session import get_db
from ..services.simulation.case_importer import case_importer

router = APIRouter(prefix="/api/simulation", tags=["simulation"])


class CaseCreate(BaseModel):
    case_name: str
    case_code: Optional[str] = None
    description: str = ""
    domain: str = "structural"
    application: str = ""
    software: str = ""
    software_version: str = ""
    related_specs: List[str] = []
    related_sections: List[str] = []
    inputs: Dict[str, Any] = {}
    project_code: str = ""
    confidence_level: str = "初步"


class CaseUpdate(BaseModel):
    case_name: Optional[str] = None
    description: Optional[str] = None
    domain: Optional[str] = None
    application: Optional[str] = None
    related_specs: Optional[List[str]] = None
    related_sections: Optional[List[str]] = None
    confidence_level: Optional[str] = None
    inputs: Optional[Dict[str, Any]] = None
    outputs: Optional[Dict[str, Any]] = None


class SpecLinkRequest(BaseModel):
    spec_ids: List[str]
    section_ids: List[str] = []


def _case_dict(c: SimulationCase) -> Dict:
    return {
        "id": c.id, "case_name": c.case_name, "case_code": c.case_code,
        "description": c.description, "domain": c.domain, "application": c.application,
        "software": c.software, "software_version": c.software_version,
        "related_specs": c.related_specs, "related_sections": c.related_sections,
        "inputs": c.inputs, "outputs": c.outputs, "images": c.images,
        "project_code": c.project_code, "confidence_level": c.confidence_level,
        "author_id": c.author_id, "tenant_id": c.tenant_id,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


@router.post("/cases")
async def create_case(
    body: CaseCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    case = SimulationCase(
        id=str(uuid.uuid4()),
        author_id=user.id,
        tenant_id=getattr(user, "tenant_id", None),
        **body.model_dump(),
    )
    db.add(case)
    await db.commit()
    await db.refresh(case)
    return _case_dict(case)


@router.get("/cases")
async def list_cases(
    domain: Optional[str] = None,
    application: Optional[str] = None,
    software: Optional[str] = None,
    q: Optional[str] = None,
    skip: int = 0, limit: int = 50,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = select(SimulationCase)
    filters = []
    if domain:
        filters.append(SimulationCase.domain == domain)
    if application:
        filters.append(SimulationCase.application == application)
    if software:
        filters.append(SimulationCase.software == software)
    if q:
        filters.append(SimulationCase.case_name.ilike(f"%{q}%"))
    if filters:
        stmt = stmt.where(and_(*filters))
    stmt = stmt.order_by(SimulationCase.created_at.desc()).offset(skip).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()
    return [_case_dict(c) for c in rows]


@router.get("/cases/{case_id}")
async def get_case(
    case_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    c = await db.get(SimulationCase, case_id)
    if not c:
        raise HTTPException(404, "案例不存在")
    return _case_dict(c)


@router.put("/cases/{case_id}")
async def update_case(
    case_id: str,
    body: CaseUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    c = await db.get(SimulationCase, case_id)
    if not c:
        raise HTTPException(404, "案例不存在")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(c, k, v)
    await db.commit()
    await db.refresh(c)
    return _case_dict(c)


@router.delete("/cases/{case_id}")
async def delete_case(
    case_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    c = await db.get(SimulationCase, case_id)
    if not c:
        raise HTTPException(404, "案例不存在")
    await db.delete(c)
    await db.commit()
    return {"deleted": case_id}


@router.post("/cases/{case_id}/import-file")
async def import_file(
    case_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    import tempfile, os
    suffix = os.path.splitext(file.filename or "")[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    try:
        c = await db.get(SimulationCase, case_id)
        if not c:
            raise HTTPException(404, "案例不存在")
        result = await case_importer.import_case(
            db, tmp_path,
            {"case_name": c.case_name, "domain": c.domain,
             "author_id": user.id, "tenant_id": getattr(user, "tenant_id", None)},
        )
        await db.commit()
    finally:
        os.unlink(tmp_path)
    return result


@router.get("/cases/{case_id}/results")
async def get_results(
    case_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = (await db.execute(
        select(SimulationResult).where(SimulationResult.case_id == case_id)
    )).scalars().all()
    return [
        {"id": r.id, "result_type": r.result_type, "result_name": r.result_name,
         "max_value": r.max_value, "min_value": r.min_value, "avg_value": r.avg_value,
         "unit": r.unit, "pass_status": r.pass_status, "distribution": r.distribution}
        for r in rows
    ]


@router.get("/cases/{case_id}/images")
async def get_images(
    case_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    c = await db.get(SimulationCase, case_id)
    if not c:
        raise HTTPException(404, "案例不存在")
    return {"images": c.images or []}


@router.post("/cases/{case_id}/link-to-spec")
async def link_to_spec(
    case_id: str,
    body: SpecLinkRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    c = await db.get(SimulationCase, case_id)
    if not c:
        raise HTTPException(404, "案例不存在")
    existing_specs = list(c.related_specs or [])
    for s in body.spec_ids:
        if s not in existing_specs:
            existing_specs.append(s)
    c.related_specs = existing_specs
    existing_secs = list(c.related_sections or [])
    for s in body.section_ids:
        if s not in existing_secs:
            existing_secs.append(s)
    c.related_sections = existing_secs
    await db.commit()
    return {"spec_ids": c.related_specs, "section_ids": c.related_sections}
