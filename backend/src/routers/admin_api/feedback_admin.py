"""
src/routers/admin_api/feedback_admin.py
管理员反馈分析接口：错误案例、高错误率章节、解决标记
"""
from __future__ import annotations

import json
import logging
from collections import defaultdict

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.deps import get_admin_user
from ...db.session import get_db
from ...routers.feedback import QueryFeedback

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/feedback", tags=["admin-feedback"])


@router.get("/overview-stats")
async def overview_stats(db: AsyncSession = Depends(get_db), _=Depends(get_admin_user)):
    """总体统计：总量、平均评分、准确率分布、错误类型分布。"""
    result = await db.execute(
        select(
            func.count().label("total"),
            func.avg(func.cast(QueryFeedback.rating, "FLOAT")).label("avg_rating"),
        )
    )
    row = result.one()

    acc_result = await db.execute(
        select(QueryFeedback.accuracy, func.count().label("cnt"))
        .where(QueryFeedback.accuracy.isnot(None))
        .group_by(QueryFeedback.accuracy)
    )
    accuracy_dist = {r.accuracy: r.cnt for r in acc_result.all()}

    err_result = await db.execute(
        select(QueryFeedback.error_types)
        .where(QueryFeedback.error_types.isnot(None))
    )
    error_type_counts: dict[str, int] = defaultdict(int)
    for (et,) in err_result.all():
        try:
            for t in json.loads(et or "[]"):
                error_type_counts[t] += 1
        except Exception:
            pass

    pos_neg = await db.execute(
        select(
            func.sum(func.cast(QueryFeedback.rating == 1, "INTEGER")).label("positive"),
            func.sum(func.cast(QueryFeedback.rating == -1, "INTEGER")).label("negative"),
        )
    )
    pn = pos_neg.one()

    return {
        "total":          row.total or 0,
        "avg_rating":     round(float(row.avg_rating), 2) if row.avg_rating else None,
        "positive":       int(pn.positive or 0),
        "negative":       int(pn.negative or 0),
        "accuracy_dist":  accuracy_dist,
        "error_type_dist": dict(sorted(error_type_counts.items(), key=lambda x: -x[1])),
    }


@router.get("/error-cases")
async def error_cases(
    accuracy:   str | None = Query(None, description="correct/partial/wrong"),
    error_type: str | None = Query(None, description="错误类型筛选"),
    limit: int = Query(50, le=200),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_admin_user),
):
    """错误案例列表，支持按准确性和错误类型筛选。"""
    stmt = (
        select(QueryFeedback)
        .where(
            (QueryFeedback.accuracy.in_(["partial", "wrong"]))
            | (QueryFeedback.rating == -1)
        )
        .order_by(QueryFeedback.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if accuracy:
        stmt = select(QueryFeedback).where(QueryFeedback.accuracy == accuracy).order_by(
            QueryFeedback.created_at.desc()).limit(limit).offset(offset)

    result = await db.execute(stmt)
    rows = result.scalars().all()

    cases = []
    for r in rows:
        if error_type:
            types = json.loads(r.error_types or "[]")
            if error_type not in types:
                continue
        cases.append({
            "id":             r.id,
            "question":       r.question,
            "answer":         r.answer[:300],
            "rating":         r.rating,
            "accuracy":       r.accuracy,
            "error_types":    json.loads(r.error_types or "[]"),
            "correct_answer": r.correct_answer,
            "comment":        r.comment_text,
            "strategy":       r.strategy,
            "status":         r.feedback_status,
            "created_at":     r.created_at.isoformat() if r.created_at else None,
        })
    return {"items": cases, "total": len(cases)}


@router.get("/problematic-chunks")
async def problematic_chunks(
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_admin_user),
):
    """统计来源章节的错误率，找出高错误率 chunk。"""
    neg_result = await db.execute(
        select(QueryFeedback.sources)
        .where(
            (QueryFeedback.rating == -1)
            | (QueryFeedback.accuracy.in_(["partial", "wrong"]))
        )
    )
    pos_result = await db.execute(
        select(QueryFeedback.sources)
        .where(QueryFeedback.rating == 1)
    )

    chunk_neg: dict[str, int] = defaultdict(int)
    chunk_pos: dict[str, int] = defaultdict(int)

    for (src_json,) in neg_result.all():
        for src in json.loads(src_json or "[]"):
            cid = src.get("chunk_id") or src.get("doc_id")
            if cid:
                chunk_neg[cid] += 1

    for (src_json,) in pos_result.all():
        for src in json.loads(src_json or "[]"):
            cid = src.get("chunk_id") or src.get("doc_id")
            if cid:
                chunk_pos[cid] += 1

    all_chunks = set(chunk_neg) | set(chunk_pos)
    results = []
    for cid in all_chunks:
        neg = chunk_neg.get(cid, 0)
        pos = chunk_pos.get(cid, 0)
        total = neg + pos
        if total < 2:
            continue
        results.append({
            "chunk_id":   cid,
            "total":      total,
            "errors":     neg,
            "error_rate": round(neg / total, 3),
        })

    results.sort(key=lambda x: -x["error_rate"])
    return {"items": results[:limit]}


@router.post("/resolve")
async def resolve_feedback(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_admin_user),
):
    """将指定反馈标记为已处理。"""
    feedback_id = payload.get("feedback_id")
    note = payload.get("note", "")
    if not feedback_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="feedback_id required")

    result = await db.execute(select(QueryFeedback).where(QueryFeedback.id == feedback_id))
    fb = result.scalar_one_or_none()
    if fb is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="feedback not found")

    fb.feedback_status = "resolved"
    if note:
        fb.comment_text = (fb.comment_text or "") + f"\n[已处理] {note}"
    await db.commit()
    return {"status": "OK"}
