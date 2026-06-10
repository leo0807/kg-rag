"""Admin API — 评测数据集管理 (E1)"""
from __future__ import annotations

import csv
import io
import json
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.deps import get_admin_user
from ...db.eval_models import EvalDataset, EvalQuestion
from ...db.models import User
from ...db.session import get_db
from ...services.evaluation.dataset_importer import importer
from ...services.evaluation.dataset_schema import EvalQuestionModel

router = APIRouter(prefix="/api/admin/eval/datasets", tags=["admin-eval"])


# ── helpers ───────────────────────────────────────────────────────────────────

def _ds_summary(ds: EvalDataset) -> dict:
    return {
        "id": ds.id, "name": ds.name, "version": ds.version,
        "description": ds.description, "total_count": ds.total_count,
        "type_distribution": ds.type_distribution,
        "difficulty_distribution": ds.difficulty_distribution,
        "source_doc_ids": ds.source_doc_ids,
        "created_at": ds.created_at.isoformat() if ds.created_at else None,
    }


async def _save_dataset(db: AsyncSession, dataset_model, user_id: str) -> EvalDataset:
    ds = EvalDataset(
        id=dataset_model.id, name=dataset_model.name,
        version=dataset_model.version, description=dataset_model.description,
        source_doc_ids=dataset_model.source_doc_ids,
        total_count=dataset_model.total_count,
        type_distribution=dataset_model.type_distribution,
        difficulty_distribution=dataset_model.difficulty_distribution,
        created_by=user_id,
    )
    db.add(ds)
    for q in dataset_model.questions:
        db.add(EvalQuestion(
            id=q.id, dataset_id=ds.id, question_type=q.question_type,
            stem=q.stem, options=q.options, correct_answer=q.correct_answer,
            explanation=q.explanation, source_doc_id=q.source_doc_id,
            source_section=q.source_section, difficulty=q.difficulty,
            tags=q.tags, order_index=q.order_index,
        ))
    await db.commit()
    await db.refresh(ds)
    return ds


# ── routes ────────────────────────────────────────────────────────────────────

@router.post("")
async def upload_dataset(
    file: UploadFile = File(...),
    name: str = Form(""),
    description: str = Form(""),
    source_doc_id: str = Form(""),
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    data = await file.read()
    ds_model = importer.from_bytes(data, file.filename or "upload", name or "")
    if description:
        ds_model.description = description
    if source_doc_id:
        ds_model.source_doc_ids = [source_doc_id]

    report = importer.validate(ds_model)
    if not report.valid:
        msgs = "; ".join(f"第{e.question_index+1}题: {e.message}" for e in report.errors[:5])
        raise HTTPException(400, f"数据集验证失败: {msgs}")

    ds = await _save_dataset(db, ds_model, admin.id)
    return {**_ds_summary(ds), "warnings": report.warnings}


@router.get("")
async def list_datasets(
    _admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(
        select(EvalDataset).order_by(EvalDataset.created_at.desc())
    )).scalars().all()
    return [_ds_summary(r) for r in rows]


@router.get("/{ds_id}")
async def get_dataset(ds_id: str, _admin: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    ds = await db.get(EvalDataset, ds_id)
    if not ds:
        raise HTTPException(404, "数据集不存在")
    return _ds_summary(ds)


@router.get("/{ds_id}/questions")
async def list_questions(
    ds_id: str, page: int = 1, page_size: int = 50,
    _admin: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db),
):
    total = (await db.execute(
        select(EvalQuestion).where(EvalQuestion.dataset_id == ds_id)
    )).scalars().all()
    offset = (page - 1) * page_size
    rows = total[offset: offset + page_size]
    return {
        "total": len(total), "page": page, "page_size": page_size,
        "questions": [
            {"id": q.id, "stem": q.stem, "question_type": q.question_type,
             "options": q.options, "correct_answer": q.correct_answer,
             "difficulty": q.difficulty, "source_doc_id": q.source_doc_id,
             "explanation": q.explanation, "order_index": q.order_index}
            for q in rows
        ],
    }


class QuestionPatch(BaseModel):
    stem: Optional[str] = None
    correct_answer: Optional[str] = None
    explanation: Optional[str] = None
    difficulty: Optional[str] = None


@router.put("/{ds_id}/questions/{qid}")
async def update_question(
    ds_id: str, qid: str, patch: QuestionPatch,
    _admin: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db),
):
    q = await db.get(EvalQuestion, qid)
    if not q or q.dataset_id != ds_id:
        raise HTTPException(404, "题目不存在")
    for field, val in patch.model_dump(exclude_none=True).items():
        setattr(q, field, val)
    await db.commit()
    return {"ok": True}


@router.delete("/{ds_id}")
async def delete_dataset(ds_id: str, _admin: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    await db.execute(delete(EvalQuestion).where(EvalQuestion.dataset_id == ds_id))
    await db.execute(delete(EvalDataset).where(EvalDataset.id == ds_id))
    await db.commit()
    return {"ok": True}


@router.post("/{ds_id}/export")
async def export_dataset(ds_id: str, _admin: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    ds = await db.get(EvalDataset, ds_id)
    if not ds:
        raise HTTPException(404, "数据集不存在")
    rows = (await db.execute(
        select(EvalQuestion).where(EvalQuestion.dataset_id == ds_id).order_by(EvalQuestion.order_index)
    )).scalars().all()
    out = io.StringIO()
    w = csv.DictWriter(out, fieldnames=["stem", "A", "B", "C", "D", "correct_answer",
                                        "explanation", "difficulty", "source_doc_id", "question_type"])
    w.writeheader()
    for q in rows:
        opts = q.options or {}
        w.writerow({"stem": q.stem, "A": opts.get("A",""), "B": opts.get("B",""),
                    "C": opts.get("C",""), "D": opts.get("D",""),
                    "correct_answer": q.correct_answer, "explanation": q.explanation,
                    "difficulty": q.difficulty, "source_doc_id": q.source_doc_id,
                    "question_type": q.question_type})
    out.seek(0)
    return StreamingResponse(iter([out.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f"attachment; filename=dataset_{ds_id}.csv"})


@router.post("/{ds_id}/validate")
async def validate_dataset(ds_id: str, _admin: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    ds = await db.get(EvalDataset, ds_id)
    if not ds:
        raise HTTPException(404, "数据集不存在")
    rows = (await db.execute(
        select(EvalQuestion).where(EvalQuestion.dataset_id == ds_id)
    )).scalars().all()
    missing_answer = sum(1 for q in rows if not q.correct_answer)
    missing_stem   = sum(1 for q in rows if not q.stem)
    return {"total": len(rows), "missing_answer": missing_answer,
            "missing_stem": missing_stem, "valid": missing_answer == 0 and missing_stem == 0}
