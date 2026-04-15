"""
数据库模型：用户、用户配置、系统配置、审计日志、对话、反馈
"""
import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Boolean, ForeignKey, func, Index, Integer, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base


class User(Base):
    __tablename__ = "users"

    id:         Mapped[str]           = mapped_column(String(36), primary_key=True)
    username:   Mapped[str]           = mapped_column(String(6), unique=True, index=True)
    email:      Mapped[str]           = mapped_column(String(128), unique=True, index=True)
    hashed_pw:  Mapped[str]           = mapped_column(String(256))
    full_name:  Mapped[str]           = mapped_column(String(64), default="")
    department: Mapped[str]           = mapped_column(String(64), default="")
    is_admin:   Mapped[bool]          = mapped_column(Boolean, default=False)
    is_active:  Mapped[bool]          = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime]      = mapped_column(DateTime, server_default=func.now())

    settings:   Mapped[list["UserSetting"]] = relationship(back_populates="user")
    audit_logs: Mapped[list["AuditLog"]]    = relationship(back_populates="user")


class SystemSetting(Base):
    __tablename__ = "system_settings"

    key:         Mapped[str]      = mapped_column(String(128), primary_key=True)
    value:       Mapped[str]      = mapped_column(Text)
    description: Mapped[str]      = mapped_column(Text, default="")
    updated_at:  Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class UserSetting(Base):
    __tablename__ = "user_settings"

    user_id:    Mapped[str]      = mapped_column(String(36), ForeignKey("users.id"), primary_key=True)
    key:        Mapped[str]      = mapped_column(String(128), primary_key=True)
    value:      Mapped[str]      = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="settings")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id:         Mapped[int]      = mapped_column(primary_key=True, autoincrement=True)
    user_id:    Mapped[str]      = mapped_column(String(36), ForeignKey("users.id"))
    action:     Mapped[str]      = mapped_column(String(64))
    resource:   Mapped[str]      = mapped_column(String(128))
    detail:     Mapped[str]      = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="audit_logs")


class Conversation(Base):
    __tablename__  = "conversations"
    __table_args__ = (Index("ix_conversations_user_id", "user_id"),)

    id:         Mapped[str]      = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id:    Mapped[str]      = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    title:      Mapped[str]      = mapped_column(String(100), default="新对话")
    messages:   Mapped[str]      = mapped_column(Text, default="[]")
    strategy:   Mapped[str]      = mapped_column(String(32), default="parallel")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class LLMUsage(Base):
    """每次 LLM 调用的 token 用量与费用记录，用于成本分摊报表"""
    __tablename__  = "llm_usage"
    __table_args__ = (
        Index("ix_llm_usage_user_id",    "user_id"),
        Index("ix_llm_usage_created_at", "created_at"),
    )

    id:                Mapped[int]      = mapped_column(Integer,      primary_key=True, autoincrement=True)
    user_id:           Mapped[str]      = mapped_column(String(36),   nullable=True)
    department:        Mapped[str]      = mapped_column(String(64),   default="")
    model:             Mapped[str]      = mapped_column(String(128))
    prompt_tokens:     Mapped[int]      = mapped_column(Integer,      default=0)
    completion_tokens: Mapped[int]      = mapped_column(Integer,      default=0)
    cost_usd:          Mapped[float]    = mapped_column(Float,        default=0.0)
    strategy:          Mapped[str]      = mapped_column(String(32),   default="")
    latency_ms:        Mapped[int]      = mapped_column(Integer,      default=0)
    question_preview:  Mapped[str]      = mapped_column(String(200),  default="")
    created_at:        Mapped[datetime] = mapped_column(DateTime,     server_default=func.now())


class CacheHit(Base):
    """语义缓存命中记录，用于统计缓存节省的 token 和费用"""
    __tablename__  = "cache_hits"
    __table_args__ = (
        Index("ix_cache_hits_user_id",    "user_id"),
        Index("ix_cache_hits_created_at", "created_at"),
    )

    id:                       Mapped[int]      = mapped_column(Integer,     primary_key=True, autoincrement=True)
    user_id:                  Mapped[str]      = mapped_column(String(36),  nullable=True)
    department:               Mapped[str]      = mapped_column(String(64),  default="")
    question_preview:         Mapped[str]      = mapped_column(String(200), default="")
    matched_question_preview: Mapped[str]      = mapped_column(String(200), default="")
    similarity:               Mapped[float]    = mapped_column(Float,       default=0.0)
    strategy:                 Mapped[str]      = mapped_column(String(32),  default="")
    cache_id:                 Mapped[str]      = mapped_column(String(36),  default="")
    prompt_tokens_saved:      Mapped[int]      = mapped_column(Integer,     default=0)
    cost_saved_usd:           Mapped[float]    = mapped_column(Float,       default=0.0)
    created_at:               Mapped[datetime] = mapped_column(DateTime,    server_default=func.now())


class NodeAnnotation(Base):
    """图谱节点批注 — 用户对知识节点的现场心得与纠错备注"""
    __tablename__  = "node_annotations"
    __table_args__ = (
        Index("ix_node_annotations_node_id",    "node_id"),
        Index("ix_node_annotations_user_id",    "user_id"),
        Index("ix_node_annotations_created_at", "created_at"),
    )

    id:         Mapped[int]      = mapped_column(Integer,     primary_key=True, autoincrement=True)
    node_id:    Mapped[str]      = mapped_column(String(256), nullable=False)   # chunk_id or entity name
    node_type:  Mapped[str]      = mapped_column(String(32),  default="")       # Section / Tool / Material / …
    user_id:    Mapped[str]      = mapped_column(String(36),  ForeignKey("users.id"), nullable=False)
    content:    Mapped[str]      = mapped_column(Text,        nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime,    server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime,    server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship()

