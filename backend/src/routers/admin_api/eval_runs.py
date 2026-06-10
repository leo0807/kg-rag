"""Admin API — 评测运行管理 (E2 + E3 + E4 + E5)"""
from __future__ import annotations

import csv
import io
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.deps import get_admin_user
from ...db.eval_models import EvalDataset, EvalErrorAnalysis, EvalQuestion, EvalResult, EvalRun
from ...db.models import User
from ...db.session import get_db
from ...services.evaluation.eval_config import EvalRunConfig
from ...services.evaluation.eval_runner import cancel_run, start_eval_run

router = APIRouter(prefix="/api/admin/eval/runs", tags=["admin-eval"])


def _run_summary(r: EvalRun) -> dict:
    return {
        "id": r.id, "run_name": r.run_name, "description": r.description,
        "dataset_id": r.dataset_id, "status": r.status,
        "progress": r.progress, "total_questions": r.total_questions,
        "completed_questions": r.completed_questions,
        "accuracy": r.accuracy, "accuracy_by_type": r.accuracy_by_type,
        "avg_latency_ms": r.avg_latency_ms, "p95_latency_ms": r.p95_latency_ms,
        "tags": r.tags, "git_commit": r.git_commit,
        "started_at":   r.started_at.isoformat()  if r.started_at   else None,
        "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        "created_at":   r.created_at.isoformat()   if r.created_at   else None,
    }


class RunCreateBody(BaseModel):
    dataset_id: str
    strategy: str = "parallel"
    top_k: int = 5
    use_reranker: bool = True
    source_doc_id: str = ""
    concurrency: int = 3
    run_name: str = ""
    description: str = ""
    tags: list[str] = []


# ── CRUD ─────────────────────────────────────────────────────────────────────

@router.post("")
async def create_run(
    body: RunCreateBody,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    ds = await db.get(EvalDataset, body.dataset_id)
    if not ds:
        raise HTTPException(404, "数据集不存在")
    config = EvalRunConfig(**body.model_dump())
    run_id = await start_eval_run(config, admin.id)
    return {"run_id": run_id, "status": "running"}


@router.get("")
async def list_runs(
    dataset_id: Optional[str] = None,
    _admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(EvalRun).order_by(EvalRun.created_at.desc())
    if dataset_id:
        q = q.where(EvalRun.dataset_id == dataset_id)
    rows = (await db.execute(q)).scalars().all()
    return [_run_summary(r) for r in rows]


@router.get("/{run_id}")
async def get_run(run_id: str, _admin: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    r = await db.get(EvalRun, run_id)
    if not r:
        raise HTTPException(404, "评测运行不存在")
    return _run_summary(r)


@router.get("/{run_id}/results")
async def get_run_results(
    run_id: str, correct: Optional[bool] = None, page: int = 1, page_size: int = 50,
    _admin: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db),
):
    q = select(EvalResult).where(EvalResult.run_id == run_id)
    if correct is not None:
        q = q.where(EvalResult.is_correct == correct)
    all_rows = (await db.execute(q)).scalars().all()
    offset = (page - 1) * page_size
    rows = all_rows[offset: offset + page_size]

    qids = {r.question_id for r in rows}
    qs = {q.id: q for q in (await db.execute(
        select(EvalQuestion).where(EvalQuestion.id.in_(qids))
    )).scalars().all()} if qids else {}

    return {
        "total": len(all_rows), "page": page, "page_size": page_size,
        "results": [
            {"id": r.id, "question_id": r.question_id,
             "stem": qs.get(r.question_id, {}).stem if hasattr(qs.get(r.question_id, object()), 'stem') else "",
             "correct_answer": qs[r.question_id].correct_answer if r.question_id in qs else "",
             "predicted_answer": r.predicted_answer, "is_correct": r.is_correct,
             "reasoning": r.reasoning, "sources": r.sources,
             "latency_ms": r.latency_ms, "error_type": r.error_type}
            for r in rows
        ],
    }


@router.post("/{run_id}/cancel")
async def cancel_run_api(run_id: str, _admin: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    r = await db.get(EvalRun, run_id)
    if not r:
        raise HTTPException(404, "评测不存在")
    cancel_run(run_id)
    return {"ok": True}


@router.post("/{run_id}/rerun")
async def rerun(run_id: str, admin: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    r = await db.get(EvalRun, run_id)
    if not r:
        raise HTTPException(404, "评测不存在")
    config = EvalRunConfig.from_dict(r.config or {})
    new_id = await start_eval_run(config, admin.id)
    return {"run_id": new_id, "status": "running"}


@router.get("/{run_id}/export")
async def export_run(run_id: str, _admin: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    results = (await db.execute(
        select(EvalResult).where(EvalResult.run_id == run_id)
    )).scalars().all()
    qids = {r.question_id for r in results}
    qs = {q.id: q for q in (await db.execute(
        select(EvalQuestion).where(EvalQuestion.id.in_(qids))
    )).scalars().all()} if qids else {}

    out = io.StringIO()
    w = csv.DictWriter(out, fieldnames=["question_id", "stem", "correct_answer",
                                        "predicted_answer", "is_correct", "latency_ms", "error_type"])
    w.writeheader()
    for r in results:
        q = qs.get(r.question_id)
        w.writerow({"question_id": r.question_id, "stem": q.stem if q else "",
                    "correct_answer": q.correct_answer if q else "",
                    "predicted_answer": r.predicted_answer, "is_correct": r.is_correct,
                    "latency_ms": r.latency_ms, "error_type": r.error_type})
    out.seek(0)
    return StreamingResponse(iter([out.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f"attachment; filename=run_{run_id}.csv"})


# ── E3 error analysis ─────────────────────────────────────────────────────────

@router.get("/{run_id}/error-analysis")
async def get_error_analysis(run_id: str, _admin: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        select(EvalErrorAnalysis).where(EvalErrorAnalysis.run_id == run_id)
    )).scalars().all()
    by_reason: dict[str, int] = {}
    for a in rows:
        by_reason[a.error_reason] = by_reason.get(a.error_reason, 0) + 1
    return {"total_errors": len(rows), "by_reason": by_reason,
            "details": [{"result_id": a.result_id, "error_reason": a.error_reason,
                         "confidence": a.confidence, "suggestions": a.suggestions} for a in rows[:20]]}


# ── E4 comparison ─────────────────────────────────────────────────────────────

class CompareBody(BaseModel):
    baseline_id: str
    target_id: str


@router.post("/compare")
async def compare_runs(
    body: CompareBody, _admin: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db),
):
    base = await db.get(EvalRun, body.baseline_id)
    tgt  = await db.get(EvalRun, body.target_id)
    if not base or not tgt:
        raise HTTPException(404, "评测运行不存在")

    base_res = {r.question_id: r for r in (await db.execute(
        select(EvalResult).where(EvalResult.run_id == body.baseline_id)
    )).scalars().all()}
    tgt_res = {r.question_id: r for r in (await db.execute(
        select(EvalResult).where(EvalResult.run_id == body.target_id)
    )).scalars().all()}

    wrong_to_right, right_to_wrong, still_wrong = [], [], []
    for qid, b in base_res.items():
        t = tgt_res.get(qid)
        if not t:
            continue
        if not b.is_correct and t.is_correct:
            wrong_to_right.append(qid)
        elif b.is_correct and not t.is_correct:
            right_to_wrong.append(qid)
        elif not b.is_correct and not t.is_correct and b.predicted_answer != t.predicted_answer:
            still_wrong.append(qid)

    acc_delta = round((tgt.accuracy or 0) - (base.accuracy or 0), 4)
    lat_delta = round((tgt.avg_latency_ms or 0) - (base.avg_latency_ms or 0), 1)
    return {
        "baseline": _run_summary(base),
        "target":   _run_summary(tgt),
        "overall": {
            "accuracy_change":   f"{acc_delta:+.1%}",
            "latency_change_ms": lat_delta,
        },
        "changed_results": {
            "wrong_to_right":  wrong_to_right,
            "right_to_wrong":  right_to_wrong,
            "still_wrong_different": still_wrong,
        },
    }


# ── E5 suggestions ────────────────────────────────────────────────────────────

@router.post("/{run_id}/analyze")
async def trigger_analysis(run_id: str, _admin: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    """Trigger error analysis for a completed run."""
    from ...services.evaluation.error_analyzer import trigger_error_analysis
    return await trigger_error_analysis(run_id)


@router.get("/{run_id}/suggestions")
async def get_suggestions(run_id: str, _admin: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    """Get optimization suggestions based on error analysis."""
    from ...services.evaluation.optimization_advisor import get_suggestions_api
    return await get_suggestions_api(run_id, db)


@router.post("/{run_id}/generate-report")
async def generate_report(
    run_id: str, fmt: str = "docx",
    _admin: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db),
):
    from ...services.evaluation.baseline_report import generate_report as _gen
    content, ctype = await _gen([run_id], fmt, db)
    ext = "docx" if "docx" in ctype else "txt"
    return StreamingResponse(iter([content]), media_type=ctype,
                             headers={"Content-Disposition": f"attachment; filename=report_{run_id}.{ext}"})
