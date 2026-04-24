"""
src/routers/feedback.py
查询结果用户反馈，支持数据飞轮
"""
import logging
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from ..db.session import get_db
from ..db.models import Base
from sqlalchemy import String, Integer, Text, DateTime, Boolean, Index
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from sqlalchemy import func
from ..auth.deps import get_current_user
from ..db.models import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/feedback", tags=["feedback"])


class QueryFeedback(Base):
    __tablename__  = "query_feedback"
    __table_args__ = (
        Index("ix_query_feedback_user_id",    "user_id"),
        Index("ix_query_feedback_created_at", "created_at"),
    )

    id:          Mapped[int]  = mapped_column(primary_key=True, autoincrement=True)
    question:    Mapped[str]  = mapped_column(Text)
    answer:      Mapped[str]  = mapped_column(Text)
    sources:     Mapped[str]  = mapped_column(Text, default="[]")
    rating:      Mapped[int]  = mapped_column(Integer)  # 1=👍 -1=👎 0=隐式（来源点击）
    strategy:    Mapped[str]  = mapped_column(String(32), default="parallel")
    user_id:     Mapped[str]  = mapped_column(String(36), default="")
    detail:      Mapped[str]  = mapped_column(Text, default="")   # 隐式反馈元数据
    created_at:  Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class FeedbackRequest(BaseModel):
    question: str
    answer:   str
    sources:  list[dict] = []
    rating:   int        # 1=👍 -1=👎 0=来源点击隐式
    strategy: str        = "parallel"
    user_id:  str        = ""
    detail:   str        = ""   # e.g. "clicked_source:CPS1220_001"


@router.post("")
async def submit_feedback(
    req: FeedbackRequest,
    db:  AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    import json
    feedback = QueryFeedback(
        question = req.question,
        answer   = req.answer,
        sources  = json.dumps(req.sources, ensure_ascii=False),
        rating   = req.rating,
        strategy = req.strategy,
        user_id  = req.user_id or user.id,
        detail   = req.detail,
    )
    db.add(feedback)
    await db.commit()
    return {"status": "OK"}


@router.get("/stats")
async def feedback_stats(db: AsyncSession = Depends(get_db)):
    """获取评分统计"""
    result = await db.execute(
        select(
            func.count().label("total"),
            func.sum(
                func.cast(QueryFeedback.rating == 1, Integer)
            ).label("positive"),
            func.sum(
                func.cast(QueryFeedback.rating == -1, Integer)
            ).label("negative"),
        )
    )
    row = result.one()
    return {
        "total":    row.total    or 0,
        "positive": row.positive or 0,
        "negative": row.negative or 0,
    }


@router.get("/export")
async def export_training_data(
    min_rating: int = 1,
    format:     str = "jsonl",   # "jsonl" | "reranker"
    db:         AsyncSession = Depends(get_db),
):
    """
    导出高质量问答对用于微调 Reranker。

    - min_rating=1  → 仅导出 👍 正向反馈
    - format=jsonl  → 每行一个 JSON，含 question/answer/sources
    - format=reranker → bge-reranker 微调格式：{"query","pos","neg"}
    """
    import json
    from fastapi.responses import StreamingResponse

    result = await db.execute(
        select(QueryFeedback)
        .where(QueryFeedback.rating >= min_rating)
        .order_by(QueryFeedback.created_at.desc())
    )
    rows = result.scalars().all()

    if format == "reranker":
        # 构造 bge-reranker 格式：正样本来自 rating=1，负样本来自 rating=-1
        pos_rows = [r for r in rows if r.rating == 1]
        neg_rows = await db.execute(
            select(QueryFeedback).where(QueryFeedback.rating == -1)
        )
        neg_map: dict[str, list[str]] = {}
        for neg in neg_rows.scalars().all():
            neg_map.setdefault(neg.question, []).append(neg.answer)

        lines = []
        for r in pos_rows:
            sources = json.loads(r.sources or "[]")
            pos_texts = [r.answer] + [s.get("title", "") for s in sources if s.get("title")]
            entry = {
                "query": r.question,
                "pos":   pos_texts[:3],
                "neg":   neg_map.get(r.question, [])[:3],
            }
            lines.append(json.dumps(entry, ensure_ascii=False))
    else:
        lines = []
        for r in rows:
            lines.append(json.dumps({
                "question":   r.question,
                "answer":     r.answer,
                "sources":    json.loads(r.sources or "[]"),
                "rating":     r.rating,
                "strategy":   r.strategy,
                "detail":     r.detail,
                "created_at": r.created_at.isoformat(),
            }, ensure_ascii=False))

    content = "\n".join(lines) + "\n"
    filename = f"training_data_{format}.jsonl"
    return StreamingResponse(
        iter([content]),
        media_type="application/x-ndjson",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
