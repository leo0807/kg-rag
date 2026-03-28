"""
数据库模型：用户、用户配置、系统配置、审计日志
"""
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Boolean, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base


class User(Base):
    __tablename__ = "users"

    id:         Mapped[str]           = mapped_column(String(36), primary_key=True)
    username:   Mapped[str]           = mapped_column(String(6), unique=True, index=True)  # 6位工号
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