"""
H1.1 / H6.1 / H7.1 / H8.2 集成相关数据模型
Integration / IntegrationLog / Webhook / WebhookDelivery /
ApiKey / ApiKeyUsage / MessageTemplate
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from .base import Base

try:
    from sqlalchemy.dialects.postgresql import JSONB as PG
except ImportError:
    from sqlalchemy import JSON as PG  # type: ignore[assignment]


def _uuid() -> str:
    return str(uuid.uuid4())


# ─────────────────────────── H1.1 集成配置 ───────────────────────────

class Integration(Base):
    __tablename__  = "integrations"
    __table_args__ = (Index("idx_integration_tenant", "tenant_id"),)

    id:          Mapped[str]      = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id:   Mapped[str|None] = mapped_column(String(36), nullable=True)
    name:        Mapped[str]      = mapped_column(String(100), nullable=False)
    type:        Mapped[str]      = mapped_column(String(50),  nullable=False)  # plm/mes/erp/sso

    endpoint:    Mapped[str|None] = mapped_column(String(500), nullable=True)
    auth_type:   Mapped[str|None] = mapped_column(String(50),  nullable=True)  # api_key/oauth2/basic/jwt
    auth_config: Mapped[Any]      = mapped_column(PG, default=dict)  # 加密存储

    status:       Mapped[str]      = mapped_column(String(20), default="inactive")
    last_sync_at: Mapped[datetime|None] = mapped_column(DateTime, nullable=True)
    last_error:   Mapped[str|None]      = mapped_column(Text, nullable=True)

    settings:   Mapped[Any]      = mapped_column(PG, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class IntegrationLog(Base):
    __tablename__  = "integration_logs"
    __table_args__ = (Index("idx_intlog_integration", "integration_id"),)

    id:             Mapped[str]      = mapped_column(String(36), primary_key=True, default=_uuid)
    integration_id: Mapped[str]      = mapped_column(String(36), nullable=False)
    direction:      Mapped[str]      = mapped_column(String(20), default="outbound")
    action:         Mapped[str]      = mapped_column(String(100), default="")
    status:         Mapped[str]      = mapped_column(String(20), default="ok")
    request_body:   Mapped[Any]      = mapped_column(PG, default=dict)
    response_body:  Mapped[Any]      = mapped_column(PG, default=dict)
    error_message:  Mapped[str|None] = mapped_column(Text, nullable=True)
    duration_ms:    Mapped[int]      = mapped_column(Integer, default=0)
    created_at:     Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# ─────────────────────────── H6.1 Webhook ───────────────────────────

class Webhook(Base):
    __tablename__  = "webhooks"
    __table_args__ = (Index("idx_webhook_tenant", "tenant_id"),)

    id:        Mapped[str]      = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str|None] = mapped_column(String(36), nullable=True)
    name:      Mapped[str]      = mapped_column(String(100), nullable=False)
    url:       Mapped[str]      = mapped_column(String(500), nullable=False)
    events:    Mapped[Any]      = mapped_column(PG, default=list)
    secret:    Mapped[str|None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool]     = mapped_column(Boolean, default=True)

    retry_policy:    Mapped[Any] = mapped_column(PG, default=dict)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=30)

    success_count:    Mapped[int]           = mapped_column(Integer, default=0)
    failure_count:    Mapped[int]           = mapped_column(Integer, default=0)
    last_triggered_at:Mapped[datetime|None] = mapped_column(DateTime, nullable=True)
    created_at:       Mapped[datetime]      = mapped_column(DateTime, server_default=func.now())


class WebhookDelivery(Base):
    __tablename__  = "webhook_deliveries"
    __table_args__ = (Index("idx_wh_delivery_webhook", "webhook_id"),)

    id:             Mapped[str]      = mapped_column(String(36), primary_key=True, default=_uuid)
    webhook_id:     Mapped[str]      = mapped_column(String(36), nullable=False)
    event_type:     Mapped[str]      = mapped_column(String(100), nullable=False)
    payload:        Mapped[Any]      = mapped_column(PG, default=dict)
    status:         Mapped[str]      = mapped_column(String(20), default="pending")
    response_status:Mapped[int|None] = mapped_column(Integer, nullable=True)
    response_body:  Mapped[str|None] = mapped_column(Text, nullable=True)
    attempt_count:  Mapped[int]      = mapped_column(Integer, default=0)
    next_retry_at:  Mapped[datetime|None] = mapped_column(DateTime, nullable=True)
    created_at:     Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at:   Mapped[datetime|None] = mapped_column(DateTime, nullable=True)


# ─────────────────────────── H7.1 API Key ───────────────────────────

class ApiKey(Base):
    __tablename__  = "api_keys"
    __table_args__ = (Index("idx_apikey_tenant", "tenant_id"),)

    id:         Mapped[str]      = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id:  Mapped[str|None] = mapped_column(String(36), nullable=True)
    user_id:    Mapped[str|None] = mapped_column(String(36), nullable=True)
    name:       Mapped[str]      = mapped_column(String(100), nullable=False)
    key_prefix: Mapped[str]      = mapped_column(String(20), nullable=False)
    key_hash:   Mapped[str]      = mapped_column(String(100), nullable=False)

    scopes:      Mapped[Any]      = mapped_column(PG, default=list)
    allowed_ips: Mapped[Any]      = mapped_column(PG, default=list)
    rate_limit:  Mapped[int]      = mapped_column(Integer, default=60)
    is_active:   Mapped[bool]     = mapped_column(Boolean, default=True)
    expires_at:  Mapped[datetime|None] = mapped_column(DateTime, nullable=True)
    last_used_at:Mapped[datetime|None] = mapped_column(DateTime, nullable=True)
    created_at:  Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ApiKeyUsage(Base):
    __tablename__  = "api_key_usage"
    __table_args__ = (Index("idx_akusage_key", "api_key_id"),)

    id:          Mapped[str]      = mapped_column(String(36), primary_key=True, default=_uuid)
    api_key_id:  Mapped[str]      = mapped_column(String(36), nullable=False)
    endpoint:    Mapped[str]      = mapped_column(String(200), default="")
    status_code: Mapped[int]      = mapped_column(Integer, default=200)
    duration_ms: Mapped[int]      = mapped_column(Integer, default=0)
    ip_address:  Mapped[str|None] = mapped_column(String(50), nullable=True)
    created_at:  Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# ─────────────────────────── H8.2 消息模板 ───────────────────────────

class MessageTemplate(Base):
    __tablename__  = "message_templates"
    __table_args__ = (Index("idx_msgtpl_tenant", "tenant_id"),)

    id:               Mapped[str]      = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id:        Mapped[str|None] = mapped_column(String(36), nullable=True)
    name:             Mapped[str]      = mapped_column(String(100), nullable=False)
    channel:          Mapped[str]      = mapped_column(String(50),  nullable=False)
    subject_template: Mapped[str|None] = mapped_column(String(500), nullable=True)
    body_template:    Mapped[str]      = mapped_column(Text, default="")
    variables:        Mapped[Any]      = mapped_column(PG, default=list)
    created_at:       Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
