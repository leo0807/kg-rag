"""F3.1 — Data retention policy model."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from .base import Base


class DataRetentionPolicy(Base):
    __tablename__ = "data_retention_policies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True,
                                    default=lambda: str(uuid.uuid4()))
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    retention_days: Mapped[int] = mapped_column(Integer, nullable=False)
    archive_before_delete: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                  server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                  server_default=func.now(),
                                                  onupdate=func.now())
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_run_deleted: Mapped[int | None] = mapped_column(Integer, nullable=True)
