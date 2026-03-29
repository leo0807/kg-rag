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
from sqlalchemy import String, Integer, Text, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from sqlalchemy import func

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/feedback", tags=["feedback"])


class QueryFeedback(Base):
    __tablename__ = "query_feedback"

    id:          Mapped[int]  = mapped_column(primary_key=True, autoincrement=True)
    question:    Mapped[str]  = mapped_column(Text)
    answer:      Mapped[str]  = mapped_column(Text)
    sources:     Mapped[str]  = mapped_column(Text, default="[]")
    rating:      Mapped[int]  = mapped_column(Integer)  # 1=👍 -1=👎
    strategy:    Mapped[str]  = mapped_column(String(32), default="parallel")
    user_id:     Mapped[str]  = mapped_column(String(36), default="")
    created_at:  Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class FeedbackRequest(BaseModel):
    question: str
    answer:   str
    sources:  list[dict] = []
    rating:   int        # 1 或 -1
    strategy: str        = "parallel"
    user_id:  str        = ""


@router.post("")
async def submit_feedback(
    req: FeedbackRequest,
    db:  AsyncSession = Depends(get_db),
):
    import json
    feedback = QueryFeedback(
        question = req.question,
        answer   = req.answer,
        sources  = json.dumps(req.sources, ensure_ascii=False),
        rating   = req.rating,
        strategy = req.strategy,
        user_id  = req.user_id,
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