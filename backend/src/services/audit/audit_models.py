"""
F1: Audit event model — immutable write-only records for compliance.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from ...db.base import Base

try:
    from sqlalchemy.dialects.postgresql import JSONB as JSON
except ImportError:
    from sqlalchemy import JSON

# ── Event-type constants ──────────────────────────────────────────────────────

class EventType:
    # Auth
    LOGIN           = "auth.login"
    LOGOUT          = "auth.logout"
    FAILED_LOGIN    = "auth.failed_login"
    PASSWORD_CHANGE = "auth.password_change"
    # Documents
    DOC_UPLOAD   = "doc.upload"
    DOC_VIEW     = "doc.view"
    DOC_EDIT     = "doc.edit"
    DOC_DELETE   = "doc.delete"
    DOC_DOWNLOAD = "doc.download"
    # Query / interaction
    QUERY    = "query.query"
    FEEDBACK = "query.feedback"
    SHARE    = "query.share"
    # Admin actions
    USER_CREATE     = "admin.user_create"
    ROLE_CHANGE     = "admin.role_change"
    PERM_GRANT      = "admin.permission_grant"
    # Data operations
    EXPORT       = "data.export"
    BULK_DELETE  = "data.bulk_delete"
    BACKUP       = "data.backup"
    # System
    CONFIG_CHANGE  = "system.config_change"
    SERVICE_RESTART = "system.service_restart"

# ── DB model ─────────────────────────────────────────────────────────────────

class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Event classification
    event_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    action: Mapped[str]     = mapped_column(String(50), nullable=False)  # create/read/update/delete/export

    # Subject (who)
    user_id:   Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    user_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    user_role: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(50), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Object (what)
    resource_type: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    resource_id:   Mapped[str | None] = mapped_column(String(200), nullable=True)
    resource_name: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Change detail
    before_state:  Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_state:   Mapped[dict | None] = mapped_column(JSON, nullable=True)
    changes:       Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Outcome
    success:       Mapped[bool]        = mapped_column(Boolean, default=True)
    error_message: Mapped[str | None]  = mapped_column(Text, nullable=True)

    # Request context
    trace_id:       Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    session_id:     Mapped[str | None] = mapped_column(String(100), nullable=True)
    request_path:   Mapped[str | None] = mapped_column(String(500), nullable=True)
    request_method: Mapped[str | None] = mapped_column(String(10), nullable=True)

    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                server_default=func.now(), index=True)

    __table_args__ = (
        Index("idx_audit_user_ts",    "user_id",      "timestamp"),
        Index("idx_audit_resource",   "resource_type","resource_id"),
        Index("idx_audit_event_ts",   "event_type",   "timestamp"),
        Index("idx_audit_trace",      "trace_id"),
    )


# ── In-process writer ─────────────────────────────────────────────────────────

async def write_audit(
    *,
    event_type: str,
    action: str,
    user_id: str | None = None,
    user_name: str | None = None,
    user_role: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    resource_name: str | None = None,
    before_state: dict | None = None,
    after_state: dict | None = None,
    changes: dict | None = None,
    success: bool = True,
    error_message: str | None = None,
    trace_id: str | None = None,
    session_id: str | None = None,
    request_path: str | None = None,
    request_method: str | None = None,
) -> None:
    """Fire-and-forget audit write — swallows exceptions to never block requests."""
    try:
        from ...db.session import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            db.add(AuditEvent(
                event_type=event_type, action=action,
                user_id=user_id, user_name=user_name, user_role=user_role,
                ip_address=ip_address, user_agent=user_agent,
                resource_type=resource_type, resource_id=resource_id,
                resource_name=resource_name,
                before_state=before_state, after_state=after_state, changes=changes,
                success=success, error_message=error_message,
                trace_id=trace_id, session_id=session_id,
                request_path=request_path, request_method=request_method,
            ))
            await db.commit()
    except Exception:
        pass  # audit must never break the application
