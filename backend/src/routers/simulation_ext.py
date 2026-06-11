"""K4/K5/K6/K7/K8: Extended simulation router — search, compare, workflows, rules, stats."""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func as sqlfunc
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import get_current_user
from ..db.models import User
from ..db.simulation_models import (
    SimulationCase, SimulationResult, SimulationRule, SimulationWorkflow,
)
from ..db.session import get_db
from ..services.simulation.parametric_search import parametric_search
from ..services.simulation.spec_linker import spec_linker
from ..services.simulation.rule_extractor import rule_extractor
from ..services.simulation.cluster_submitter import cluster_submitter

router = APIRouter(prefix="/api/simulation", tags=["simulation-ext"])


# ── K4: Parametric search ──────────────────────────────────────────────────────

class SearchCriteria(BaseModel):
    domain: Optional[str] = None
    application: Optional[str] = None
    software: Optional[str] = None
    material: Optional[str] = None
    load_type: Optional[str] = None
    temperature_range: Optional[List[float]] = None
    pressure_range: Optional[List[float]] = None
    confidence_level: Optional[str] = None
    project_code: Optional[str] = None
    skip: int = 0
    limit: int = 30


@router.post("/search")
async def search_cases(
    body: SearchCriteria,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await parametric_search.search(db, body.model_dump(exclude_none=True))


@router.get("/gaps")
async def parameter_gaps(
    domain: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await parametric_search.suggest_gaps(db, domain)


# ── K3: Auto-link ─────────────────────────────────────────────────────────────

@router.post("/cases/{case_id}/auto-link")
async def auto_link(
    case_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    matches = await spec_linker.auto_link(db, case_id)
    return {"case_id": case_id, "matches": matches}


# ── K5: Compare ───────────────────────────────────────────────────────────────

class CompareRequest(BaseModel):
    case_ids: List[str]


@router.post("/compare")
async def compare_cases(
    body: CompareRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if len(body.case_ids) < 2 or len(body.case_ids) > 4:
        raise HTTPException(400, "case_ids 需为 2-4 个")

    result = []
    for cid in body.case_ids:
        c = await db.get(SimulationCase, cid)
        if not c:
            raise HTTPException(404, f"案例 {cid} 不存在")
        results = (await db.execute(
            select(SimulationResult).where(SimulationResult.case_id == cid)
        )).scalars().all()
        result.append({
            "id": c.id, "case_name": c.case_name,
            "domain": c.domain, "software": c.software,
            "confidence_level": c.confidence_level,
            "inputs": c.inputs or {},
            "results": [
                {"result_name": r.result_name, "result_type": r.result_type,
                 "max_value": r.max_value, "min_value": r.min_value,
                 "unit": r.unit, "pass_status": r.pass_status}
                for r in results
            ],
        })
    return result


# ── K6: Workflows ─────────────────────────────────────────────────────────────

class WorkflowCreate(BaseModel):
    name: str
    description: str = ""
    doe_type: str = "latin_hypercube"
    sample_count: int = 10
    submit_target: str = "local"
    parameter_space: Dict[str, Any] = {}
    cluster_config: Dict[str, Any] = {}
    template_case_id: Optional[str] = None


@router.post("/workflows")
async def create_workflow(
    body: WorkflowCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    wf = SimulationWorkflow(
        id=str(uuid.uuid4()),
        tenant_id=getattr(user, "tenant_id", None),
        **body.model_dump(),
    )
    db.add(wf)
    await db.commit()
    await db.refresh(wf)
    return {"id": wf.id, "name": wf.name, "status": wf.status}


@router.get("/workflows")
async def list_workflows(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = (await db.execute(
        select(SimulationWorkflow).order_by(SimulationWorkflow.created_at.desc()).limit(50)
    )).scalars().all()
    return [
        {"id": w.id, "name": w.name, "description": w.description,
         "doe_type": w.doe_type, "sample_count": w.sample_count,
         "status": w.status, "total_runs": w.total_runs,
         "completed_runs": w.completed_runs, "submit_target": w.submit_target,
         "created_at": w.created_at.isoformat() if w.created_at else None}
        for w in rows
    ]


@router.post("/workflows/{wf_id}/submit")
async def submit_workflow(
    wf_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await cluster_submitter.submit_batch(db, wf_id)


@router.post("/workflows/{wf_id}/monitor")
async def monitor_workflow(
    wf_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await cluster_submitter.monitor_jobs(db, wf_id)


@router.post("/workflows/{wf_id}/collect")
async def collect_results(
    wf_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await cluster_submitter.collect_results(db, wf_id)


# ── K7: Rules ─────────────────────────────────────────────────────────────────

@router.get("/rules")
async def list_rules(
    rule_type: Optional[str] = None,
    skip: int = 0, limit: int = 50,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = select(SimulationRule).order_by(
        SimulationRule.confidence.desc()
    ).offset(skip).limit(limit)
    if rule_type:
        stmt = stmt.where(SimulationRule.rule_type == rule_type)
    rows = (await db.execute(stmt)).scalars().all()
    return [
        {"id": r.id, "rule_type": r.rule_type, "title": r.title,
         "condition": r.condition, "recommendation": r.recommendation,
         "confidence": r.confidence, "applied_count": r.applied_count,
         "source_cases": len(r.source_cases or [])}
        for r in rows
    ]


@router.post("/rules/extract")
async def extract_rules(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not user.is_admin:
        raise HTTPException(403, "需要管理员权限")
    return await rule_extractor.run_all(db)


# ── K8: Stats ─────────────────────────────────────────────────────────────────

@router.get("/stats")
async def get_stats(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    total = (await db.execute(sqlfunc.count(SimulationCase.id)
             .select())).scalar_one_or_none() or 0

    domain_rows = (await db.execute(
        select(SimulationCase.domain, sqlfunc.count(SimulationCase.id))
        .group_by(SimulationCase.domain)
    )).all()
    domain_dist = {r[0]: r[1] for r in domain_rows}

    software_rows = (await db.execute(
        select(SimulationCase.software, sqlfunc.count(SimulationCase.id))
        .where(SimulationCase.software != "")
        .group_by(SimulationCase.software)
    )).all()
    software_dist = {r[0]: r[1] for r in software_rows}

    pending = (await db.execute(
        select(sqlfunc.count(SimulationCase.id))
        .where(SimulationCase.confidence_level == "初步")
    )).scalar_one_or_none() or 0

    running_wf = (await db.execute(
        select(sqlfunc.count(SimulationWorkflow.id))
        .where(SimulationWorkflow.status == "running")
    )).scalar_one_or_none() or 0

    total_res = (await db.execute(sqlfunc.count(SimulationResult.id).select())).scalar_one_or_none() or 0
    pass_res  = (await db.execute(
        select(sqlfunc.count(SimulationResult.id))
        .where(SimulationResult.pass_status == "pass")
    )).scalar_one_or_none() or 0

    rules_applied = (await db.execute(
        select(sqlfunc.sum(SimulationRule.applied_count))
    )).scalar_one_or_none() or 0

    recent = (await db.execute(
        select(SimulationCase).order_by(SimulationCase.created_at.desc()).limit(5)
    )).scalars().all()

    return {
        "total": total,
        "pending_review": pending,
        "running_workflows": running_wf,
        "domain_dist": domain_dist,
        "software_dist": software_dist,
        "pass_rate": (pass_res / total_res) if total_res else 0.0,
        "rules_applied": rules_applied,
        "recent": [
            {"id": c.id, "case_name": c.case_name, "domain": c.domain,
             "confidence_level": c.confidence_level,
             "created_at": c.created_at.isoformat() if c.created_at else None}
            for c in recent
        ],
    }
