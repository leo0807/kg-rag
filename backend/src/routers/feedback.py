"""
src/routers/feedback.py
查询结果用户反馈，支持数据飞轮
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from ..db.session import get_db
from ..db.models import Base
from sqlalchemy import String, Integer, Text, DateTime, Index
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
    # 多维评分（功能十二）
    retrieval_score:    Mapped[int | None] = mapped_column(Integer, nullable=True)
    completeness_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    clarity_score:      Mapped[int | None] = mapped_column(Integer, nullable=True)
    graph_score:        Mapped[int | None] = mapped_column(Integer, nullable=True)
    comment_text:       Mapped[str | None] = mapped_column(Text,    nullable=True)
    sources_count:      Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 错误标注字段（模块一）
    accuracy:           Mapped[str | None] = mapped_column(String(20), nullable=True)  # correct/partial/wrong
    error_types:        Mapped[str | None] = mapped_column(Text, nullable=True)        # JSON 数组
    correct_answer:     Mapped[str | None] = mapped_column(Text, nullable=True)
    chunk_ids_json:     Mapped[str | None] = mapped_column(Text, nullable=True)        # JSON 数组
    feedback_status:    Mapped[str]        = mapped_column(String(20), default="pending")


class FeedbackAnalytics(Base):
    """定期聚合快照，用于趋势分析。"""
    __tablename__ = "feedback_analytics"

    id            : Mapped[int]        = mapped_column(primary_key=True, autoincrement=True)
    period_start  : Mapped[str]        = mapped_column(String(20))
    period_end    : Mapped[str]        = mapped_column(String(20))
    total_feedback: Mapped[int]        = mapped_column(Integer, default=0)
    avg_rating    : Mapped[float | None] = mapped_column(nullable=True)
    accuracy_dist : Mapped[str]        = mapped_column(Text, default="{}")  # JSON
    top_errors    : Mapped[str]        = mapped_column(Text, default="{}")  # JSON
    created_at    : Mapped[datetime]   = mapped_column(DateTime, server_default=func.now())


class FeedbackRequest(BaseModel):
    question: str
    answer:   str
    sources:  list[dict] = []
    rating:   int        # 1=👍 -1=👎 0=来源点击隐式 0=标注
    strategy: str        = "parallel"
    user_id:  str        = ""
    detail:   str        = ""
    # 可选标注字段（📝 流程）
    accuracy:       str | None  = None
    error_types:    list[str]   = []
    correct_answer: str | None  = None
    chunk_ids:      list[str]   = []


@router.post("")
async def submit_feedback(
    req: FeedbackRequest,
    db:  AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    import json
    feedback = QueryFeedback(
        question        = req.question,
        answer          = req.answer,
        sources         = json.dumps(req.sources, ensure_ascii=False),
        rating          = req.rating,
        strategy        = req.strategy,
        user_id         = req.user_id or user.id,
        detail          = req.detail,
        sources_count   = len(req.sources),
        accuracy        = req.accuracy,
        error_types     = json.dumps(req.error_types, ensure_ascii=False) if req.error_types else None,
        correct_answer  = req.correct_answer,
        chunk_ids_json  = json.dumps(req.chunk_ids) if req.chunk_ids else None,
        feedback_status = "annotated" if (req.accuracy or req.error_types) else "pending",
    )
    db.add(feedback)
    await db.flush()
    await db.commit()
    return {"status": "OK", "id": feedback.id}


class DetailedFeedbackRequest(BaseModel):
    query_id:           int
    retrieval_score:    int | None = None
    completeness_score: int | None = None
    clarity_score:      int | None = None
    graph_score:        int | None = None
    comment:            str | None = None


@router.post("/detailed")
async def submit_detailed_feedback(
    req: DetailedFeedbackRequest,
    db:  AsyncSession = Depends(get_db),
):
    from fastapi import HTTPException
    result = await db.execute(select(QueryFeedback).where(QueryFeedback.id == req.query_id))
    fb = result.scalar_one_or_none()
    if fb is None:
        raise HTTPException(status_code=404, detail="feedback not found")
    for attr, val in [
        ("retrieval_score",    req.retrieval_score),
        ("completeness_score", req.completeness_score),
        ("clarity_score",      req.clarity_score),
        ("graph_score",        req.graph_score),
        ("comment_text",       req.comment),
    ]:
        if val is not None:
            setattr(fb, attr, val)
    await db.commit()
    return {"status": "OK"}


@router.get("/detailed-stats")
async def detailed_feedback_stats(db: AsyncSession = Depends(get_db)):
    """Per-dimension averages and low-score questions."""
    result = await db.execute(
        select(
            func.avg(QueryFeedback.retrieval_score).label("avg_retrieval"),
            func.avg(QueryFeedback.completeness_score).label("avg_completeness"),
            func.avg(QueryFeedback.clarity_score).label("avg_clarity"),
            func.avg(QueryFeedback.graph_score).label("avg_graph"),
        )
    )
    row = result.one()

    low_result = await db.execute(
        select(
            QueryFeedback.question, QueryFeedback.retrieval_score,
            QueryFeedback.completeness_score, QueryFeedback.clarity_score,
            QueryFeedback.graph_score, QueryFeedback.created_at,
        )
        .where(
            (QueryFeedback.retrieval_score <= 2) | (QueryFeedback.completeness_score <= 2) |
            (QueryFeedback.clarity_score <= 2)   | (QueryFeedback.graph_score <= 2)
        )
        .order_by(QueryFeedback.created_at.desc())
        .limit(20)
    )
    low_rows = low_result.all()

    def safe(v): return round(float(v), 2) if v is not None else None

    return {
        "averages": {
            "retrieval":    safe(row.avg_retrieval),
            "completeness": safe(row.avg_completeness),
            "clarity":      safe(row.avg_clarity),
            "graph":        safe(row.avg_graph),
        },
        "low_score_questions": [
            {
                "question":   r.question,
                "scores":     {"retrieval": r.retrieval_score, "completeness": r.completeness_score,
                               "clarity": r.clarity_score, "graph": r.graph_score},
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in low_rows
        ],
    }


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
