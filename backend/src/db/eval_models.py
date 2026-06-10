"""
评测体系 DB 模型（模块E）
eval_datasets / eval_questions / eval_runs / eval_results / eval_error_analysis
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from .base import Base

try:
    from sqlalchemy.dialects.postgresql import JSONB as JSON
except ImportError:
    from sqlalchemy import JSON


def _uuid() -> str:
    return str(uuid.uuid4())


class EvalDataset(Base):
    """评测数据集目录表。"""
    __tablename__ = "eval_datasets"
    __table_args__ = (Index("ix_eval_datasets_created_at", "created_at"),)

    id:                      Mapped[str]      = mapped_column(String(36), primary_key=True, default=_uuid)
    name:                    Mapped[str]      = mapped_column(String(200), nullable=False)
    version:                 Mapped[str]      = mapped_column(String(50), default="1.0")
    description:             Mapped[str]      = mapped_column(Text, default="")
    source_doc_ids:          Mapped[Any]      = mapped_column(JSON, default=list)
    total_count:             Mapped[int]      = mapped_column(Integer, default=0)
    type_distribution:       Mapped[Any]      = mapped_column(JSON, default=dict)
    difficulty_distribution: Mapped[Any]      = mapped_column(JSON, default=dict)
    metadata_:               Mapped[Any]      = mapped_column(JSON, default=dict, name="metadata")
    tenant_id:  Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    created_at: Mapped[datetime]   = mapped_column(DateTime, server_default=func.now())
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)


class EvalQuestion(Base):
    """评测题目表。"""
    __tablename__ = "eval_questions"
    __table_args__ = (
        Index("ix_eval_questions_dataset_id", "dataset_id"),
        Index("ix_eval_questions_type",       "question_type"),
    )

    id:             Mapped[str]      = mapped_column(String(36), primary_key=True, default=_uuid)
    dataset_id:     Mapped[str]      = mapped_column(String(36), ForeignKey("eval_datasets.id", ondelete="CASCADE"))
    question_type:  Mapped[str]      = mapped_column(String(50), default="mcq")
    stem:           Mapped[str]      = mapped_column(Text, nullable=False)
    options:        Mapped[Any]      = mapped_column(JSON, nullable=True)
    correct_answer: Mapped[str]      = mapped_column(Text, nullable=False)
    explanation:    Mapped[str]      = mapped_column(Text, default="")
    source_doc_id:  Mapped[str]      = mapped_column(String(50), default="")
    source_section: Mapped[str]      = mapped_column(String(100), default="")
    difficulty:     Mapped[str]      = mapped_column(String(20), default="medium")
    tags:           Mapped[Any]      = mapped_column(JSON, default=list)
    order_index:    Mapped[int]      = mapped_column(Integer, default=0)


class EvalRun(Base):
    """评测运行记录表。"""
    __tablename__ = "eval_runs"
    __table_args__ = (
        Index("ix_eval_runs_dataset_id",  "dataset_id"),
        Index("ix_eval_runs_created_at",  "created_at"),
        Index("ix_eval_runs_status",      "status"),
    )

    id:                   Mapped[str]         = mapped_column(String(36), primary_key=True, default=_uuid)
    run_name:             Mapped[str]         = mapped_column(String(200), default="")
    description:          Mapped[str]         = mapped_column(Text, default="")
    dataset_id:           Mapped[str]         = mapped_column(String(36), ForeignKey("eval_datasets.id"))
    config:               Mapped[Any]         = mapped_column(JSON, default=dict)
    status:               Mapped[str]         = mapped_column(String(50), default="pending")
    progress:             Mapped[int]         = mapped_column(Integer, default=0)
    total_questions:      Mapped[int]         = mapped_column(Integer, default=0)
    completed_questions:  Mapped[int]         = mapped_column(Integer, default=0)
    accuracy:             Mapped[float | None] = mapped_column(Float, nullable=True)
    accuracy_by_type:     Mapped[Any]         = mapped_column(JSON, default=dict)
    avg_latency_ms:       Mapped[float | None] = mapped_column(Float, nullable=True)
    p95_latency_ms:       Mapped[float | None] = mapped_column(Float, nullable=True)
    total_tokens:         Mapped[int]         = mapped_column(Integer, default=0)
    tags:                 Mapped[Any]         = mapped_column(JSON, default=list)
    git_commit:           Mapped[str]         = mapped_column(String(50), default="")
    error_summary:        Mapped[Any]         = mapped_column(JSON, default=dict)
    tenant_id:    Mapped[str | None]        = mapped_column(String(36), nullable=True, index=True)
    started_at:   Mapped[datetime | None]   = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None]   = mapped_column(DateTime, nullable=True)
    created_at:   Mapped[datetime]          = mapped_column(DateTime, server_default=func.now())
    created_by:           Mapped[str | None]  = mapped_column(String(36), nullable=True)


class EvalResult(Base):
    """每道题的评测结果。"""
    __tablename__ = "eval_results"
    __table_args__ = (
        Index("ix_eval_results_run_id",      "run_id"),
        Index("ix_eval_results_question_id", "question_id"),
    )

    id:               Mapped[str]         = mapped_column(String(36), primary_key=True, default=_uuid)
    run_id:           Mapped[str]         = mapped_column(String(36), ForeignKey("eval_runs.id", ondelete="CASCADE"))
    question_id:      Mapped[str]         = mapped_column(String(36))
    predicted_answer: Mapped[str]         = mapped_column(Text, default="")
    is_correct:       Mapped[bool]        = mapped_column(Boolean, default=False)
    confidence:       Mapped[float]       = mapped_column(Float, default=0.0)
    reasoning:        Mapped[str]         = mapped_column(Text, default="")
    sources:          Mapped[Any]         = mapped_column(JSON, default=list)
    latency_ms:       Mapped[int]         = mapped_column(Integer, default=0)
    tokens_used:      Mapped[int]         = mapped_column(Integer, default=0)
    error_type:       Mapped[str]         = mapped_column(String(100), default="")
    created_at:       Mapped[datetime]    = mapped_column(DateTime, server_default=func.now())


class EvalErrorAnalysis(Base):
    """错题归因分析记录。"""
    __tablename__ = "eval_error_analysis"
    __table_args__ = (Index("ix_eval_error_analysis_run_id", "run_id"),)

    id:           Mapped[str]      = mapped_column(String(36), primary_key=True, default=_uuid)
    result_id:    Mapped[str]      = mapped_column(String(36))
    run_id:       Mapped[str]      = mapped_column(String(36), ForeignKey("eval_runs.id", ondelete="CASCADE"))
    error_reason: Mapped[str]      = mapped_column(String(100), default="")
    confidence:   Mapped[float]    = mapped_column(Float, default=0.0)
    details:      Mapped[Any]      = mapped_column(JSON, default=dict)
    suggestions:  Mapped[Any]      = mapped_column(JSON, default=list)
    created_at:   Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
