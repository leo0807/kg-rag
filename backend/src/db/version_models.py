"""F6 — Document version snapshot model."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from .base import Base

try:
    from sqlalchemy.dialects.postgresql import JSONB as JSON
except ImportError:
    from sqlalchemy import JSON


class DocumentVersion(Base):
    __tablename__ = "document_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True,
                                    default=lambda: str(uuid.uuid4()))
    doc_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    version_num: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    change_summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    changed_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                  server_default=func.now())

    __table_args__ = (
        Index("idx_docver_doc_ver", "doc_id", "version_num"),
    )
