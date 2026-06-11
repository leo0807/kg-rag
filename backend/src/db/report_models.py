"""J3.1: DB models for custom reports and snapshots."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from .base import Base

try:
    from sqlalchemy.dialects.postgresql import JSONB as JSON
except ImportError:
    from sqlalchemy import JSON


def _uuid() -> str:
    return str(uuid.uuid4())


class CustomReport(Base):
    __tablename__ = "custom_reports"

    id:          Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id:   Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    name:        Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")

    config:      Mapped[Any] = mapped_column(JSON, default=dict)   # full DSL config
    layout:      Mapped[Any] = mapped_column(JSON, default=dict)   # grid layout
    filters:     Mapped[Any] = mapped_column(JSON, default=dict)   # default filters

    is_public:   Mapped[bool] = mapped_column(Boolean, default=False)
    owner_id:    Mapped[str | None] = mapped_column(String(36), nullable=True)
    shared_with: Mapped[Any] = mapped_column(JSON, default=list)

    schedule:    Mapped[Any] = mapped_column(JSON, default=dict)   # cron config
    recipients:  Mapped[Any] = mapped_column(JSON, default=list)   # email list

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ReportSnapshot(Base):
    __tablename__ = "report_snapshots"

    id:           Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    report_id:    Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    data:         Mapped[Any] = mapped_column(JSON, default=dict)
    file_path:    Mapped[str] = mapped_column(String(500), default="")
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
