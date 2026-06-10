"""
规范生成系统数据库模型：SpecTemplate + GenerationTask
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class SpecTemplate(Base):
    """规范结构模板 — 描述某类规范的章节组成和格式要求"""
    __tablename__ = "spec_templates"
    __table_args__ = (
        Index("ix_spec_templates_template_id", "template_id", unique=True),
    )

    id:            Mapped[str]      = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    template_id:   Mapped[str]      = mapped_column(String(100), nullable=False)
    name:          Mapped[str]      = mapped_column(String(200), default="")
    applicable_to: Mapped[Any]      = mapped_column(JSON, default=list)   # ["密封", "粘接"]
    structure:     Mapped[Any]      = mapped_column(JSON, default=dict)   # sections list
    sample_doc_ids:Mapped[Any]      = mapped_column(JSON, default=list)   # reference doc IDs
    tenant_id:  Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    created_at: Mapped[datetime]   = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime]   = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class GenerationTask(Base):
    """规范生成任务 — 记录生成状态、进度和结果"""
    __tablename__ = "generation_tasks"
    __table_args__ = (
        Index("ix_generation_tasks_status",     "status"),
        Index("ix_generation_tasks_created_at", "created_at"),
        Index("ix_generation_tasks_user_id",    "user_id"),
    )

    id:                Mapped[str]      = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_name:         Mapped[str]      = mapped_column(String(200), default="")
    spec_type:         Mapped[str]      = mapped_column(String(100), default="")
    template_id:       Mapped[str]      = mapped_column(String(36),  nullable=True)
    inputs:            Mapped[Any]      = mapped_column(JSON, default=dict)   # GenerationInput serialized
    status:            Mapped[str]      = mapped_column(String(50),  default="pending")
    progress:          Mapped[int]      = mapped_column(Integer,     default=0)
    current_step:      Mapped[str]      = mapped_column(String(200), default="")
    result_sections:   Mapped[Any]      = mapped_column(JSON, nullable=True)  # {section_num: content}
    validation_report: Mapped[Any]      = mapped_column(JSON, nullable=True)
    error:             Mapped[str]      = mapped_column(Text, default="")
    user_id:      Mapped[str]          = mapped_column(String(36), nullable=True)
    tenant_id:    Mapped[str | None]   = mapped_column(String(36), nullable=True, index=True)
    created_at:   Mapped[datetime]     = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[str]          = mapped_column(Text, nullable=True)
