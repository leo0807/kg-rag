"""
UX 增强数据模型：会话分类、分享链接、用户笔记、用户偏好、实验框架
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ConversationCategory(Base):
    __tablename__ = "conversation_categories"
    __table_args__ = (Index("ix_conv_categories_user_id", "user_id"),)

    id:         Mapped[str]      = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id:    Mapped[str]      = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    name:       Mapped[str]      = mapped_column(String(100), default="")
    color:      Mapped[str]      = mapped_column(String(20), default="#6366f1")
    icon:       Mapped[str]      = mapped_column(String(50), default="folder")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class SharedConversation(Base):
    __tablename__ = "shared_conversations"
    __table_args__ = (Index("ix_shared_conversations_token", "share_token"),)

    id:              Mapped[str]      = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id: Mapped[str]      = mapped_column(String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    share_token:     Mapped[str]      = mapped_column(String(50), unique=True, nullable=False, default=lambda: uuid.uuid4().hex)
    created_by:      Mapped[str]      = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    expires_at:      Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_public:       Mapped[bool]     = mapped_column(Boolean, default=True)
    view_count:      Mapped[int]      = mapped_column(Integer, default=0)
    created_at:      Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class UserNote(Base):
    __tablename__ = "user_notes"
    __table_args__ = (Index("ix_user_notes_user_id", "user_id"),)

    id:                 Mapped[str]      = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id:            Mapped[str]      = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    related_chunk_id:   Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    related_message_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    title:              Mapped[str]      = mapped_column(String(500), default="")
    content:            Mapped[str]      = mapped_column(Text, default="")
    tags:               Mapped[Any]      = mapped_column(JSON, default=list)
    visibility: Mapped[str]          = mapped_column(String(20), default="private")
    tenant_id:  Mapped[str | None]   = mapped_column(String(36), nullable=True, index=True)
    created_at: Mapped[datetime]     = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime]     = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class UserPreferences(Base):
    __tablename__ = "user_preferences"

    user_id:              Mapped[str]  = mapped_column(String(36), ForeignKey("users.id"), primary_key=True)
    theme:                Mapped[str]  = mapped_column(String(20), default="dark")
    language:             Mapped[str]  = mapped_column(String(10), default="zh-CN")
    default_strategy:     Mapped[str]  = mapped_column(String(50), default="parallel")
    show_sources:         Mapped[bool] = mapped_column(Boolean, default=True)
    show_metrics:         Mapped[bool] = mapped_column(Boolean, default=False)
    answer_style:         Mapped[str]  = mapped_column(String(20), default="professional")
    ui_density:           Mapped[str]  = mapped_column(String(20), default="comfortable")
    keyboard_shortcuts:   Mapped[Any]  = mapped_column(JSON, default=dict)
    updated_at:           Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class Experiment(Base):
    __tablename__ = "experiments"

    id:          Mapped[str]  = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name:        Mapped[str]  = mapped_column(String(100), nullable=False)
    description: Mapped[str]  = mapped_column(Text, default="")
    variants:    Mapped[Any]  = mapped_column(JSON, default=list)   # [{"name":"A","weight":50}, ...]
    metrics:     Mapped[Any]  = mapped_column(JSON, default=dict)   # aggregated results
    status:      Mapped[str]  = mapped_column(String(20), default="active")
    created_at:  Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
