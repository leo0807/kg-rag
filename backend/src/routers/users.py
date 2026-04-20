"""
src/routers/users.py
管理员用户管理、审计日志
"""
import uuid
import logging
import re
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from ..db.session import get_db
from ..db.models import User, AuditLog, UserSetting, Conversation, LLMUsage, CacheHit
from .feedback import QueryFeedback
from ..auth.deps import get_admin_user, get_current_user
from ..auth.password import hash_password
from sqlalchemy import delete

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/users", tags=["users"])


@router.delete("/me")
async def delete_me(
    db:   AsyncSession = Depends(get_db),
    user: User         = Depends(get_current_user),
):
    """用户注销（合规要求：被遗忘权）。级联删除该用户的所有对话、配置、反馈、审计日志及用量统计。"""
    user_id  = user.id
    username = user.username

    await db.execute(delete(UserSetting).where(UserSetting.user_id == user_id))
    await db.execute(delete(Conversation).where(Conversation.user_id == user_id))
    await db.execute(delete(LLMUsage).where(LLMUsage.user_id == user_id))
    await db.execute(delete(CacheHit).where(CacheHit.user_id == user_id))
    await db.execute(delete(QueryFeedback).where(QueryFeedback.user_id == user_id))
    await db.execute(delete(AuditLog).where(AuditLog.user_id == user_id))
    await db.execute(delete(User).where(User.id == user_id))
    await db.commit()

    logger.info("用户注销成功: %s (ID: %s)", username, user_id)
    return {"status": "OK", "message": "您的账号及所有关联数据已永久删除"}


class CreateUserRequest(BaseModel):
    username:   str
    password:   str
    full_name:  str = ""
    department: str = ""
    email:      str = ""
    is_admin:   bool = False

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if not re.fullmatch(r"\d{6}", v):
            raise ValueError("工号必须为6位数字")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("密码至少6位")
        return v


@router.post("")
async def create_user(
    req:   CreateUserRequest,
    db:    AsyncSession = Depends(get_db),
    admin: User         = Depends(get_admin_user),
):
    """管理员创建新用户"""
    existing = await db.execute(select(User).where(User.username == req.username))
    if existing.scalar_one_or_none():
        raise HTTPException(400, "工号已存在")

    if req.email:
        email_check = await db.execute(select(User).where(User.email == req.email))
        if email_check.scalar_one_or_none():
            raise HTTPException(400, "邮箱已被使用")

    user = User(
        id         = str(uuid.uuid4()),
        username   = req.username,
        email      = req.email or f"{req.username}@internal",
        hashed_pw  = hash_password(req.password),
        full_name  = req.full_name,
        department = req.department,
        is_admin   = req.is_admin,
        is_active  = True,
    )
    db.add(user)
    db.add(AuditLog(
        user_id  = admin.id,
        action   = "create_user",
        resource = "user",
        detail   = f"管理员 {admin.username} 创建了用户 {req.username}（{'管理员' if req.is_admin else '普通用户'}）",
    ))
    await db.commit()

    logger.info("管理员 %s 创建了用户 %s", admin.username, user.username)
    return {
        "user_id":    user.id,
        "username":   user.username,
        "full_name":  user.full_name,
        "department": user.department,
        "is_admin":   user.is_admin,
        "is_active":  user.is_active,
        "created_at": user.created_at.isoformat(),
    }


@router.get("")
async def list_users(
    db:    AsyncSession = Depends(get_db),
    admin: User         = Depends(get_admin_user),
):
    result = await db.execute(select(User).order_by(User.created_at))
    users  = result.scalars().all()
    return [
        {
            "user_id":    u.id,
            "username":   u.username,
            "full_name":  u.full_name,
            "department": u.department,
            "email":      u.email,
            "is_admin":   u.is_admin,
            "is_active":  u.is_active,
            "created_at": u.created_at.isoformat(),
        }
        for u in users
    ]


@router.put("/{user_id}/toggle")
async def toggle_user(
    user_id: str,
    db:      AsyncSession = Depends(get_db),
    admin:   User         = Depends(get_admin_user),
):
    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(404, "用户不存在")
    if target.id == admin.id:
        raise HTTPException(400, "不能禁用自己")
    target.is_active = not target.is_active
    db.add(AuditLog(
        user_id  = admin.id,
        action   = "toggle_user",
        resource = "user",
        detail   = f"{'启用' if target.is_active else '禁用'}了用户 {target.username}",
    ))
    await db.commit()
    return {"status": "OK", "user_id": target.id, "is_active": target.is_active}


@router.put("/{user_id}/admin")
async def toggle_admin(
    user_id: str,
    db:      AsyncSession = Depends(get_db),
    admin:   User         = Depends(get_admin_user),
):
    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(404, "用户不存在")
    if target.id == admin.id:
        raise HTTPException(400, "不能修改自己的管理员权限")
    target.is_admin = not target.is_admin
    db.add(AuditLog(
        user_id  = admin.id,
        action   = "toggle_admin",
        resource = "user",
        detail   = f"{'授予' if target.is_admin else '撤销'}了用户 {target.username} 的管理员权限",
    ))
    await db.commit()
    return {"status": "OK", "user_id": target.id, "is_admin": target.is_admin}


class ResetPasswordRequest(BaseModel):
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("密码至少6位")
        return v


@router.post("/{user_id}/reset-password")
async def reset_password(
    user_id: str,
    req:     ResetPasswordRequest,
    db:      AsyncSession = Depends(get_db),
    admin:   User         = Depends(get_admin_user),
):
    """管理员重置指定用户的密码"""
    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(404, "用户不存在")

    target.hashed_pw = hash_password(req.new_password)
    db.add(AuditLog(
        user_id  = admin.id,
        action   = "reset_password",
        resource = "user",
        detail   = f"管理员 {admin.username} 重置了用户 {target.username} 的密码",
    ))
    await db.commit()
    logger.info("管理员 %s 重置了用户 %s 的密码", admin.username, target.username)
    return {"status": "OK", "message": f"已重置用户 {target.username} 的密码"}


@router.get("/audit-logs")
async def get_audit_logs(
    page:     int         = 1,
    per_page: int         = 20,
    db:       AsyncSession = Depends(get_db),
    admin:    User         = Depends(get_admin_user),
):
    count_result = await db.execute(select(func.count()).select_from(AuditLog))
    total        = count_result.scalar()

    result = await db.execute(
        select(AuditLog, User.username, User.full_name)
        .join(User, AuditLog.user_id == User.id)
        .order_by(desc(AuditLog.created_at))
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    rows = result.all()

    return {
        "data": [
            {
                "id":         row.AuditLog.id,
                "username":   row.username,
                "full_name":  row.full_name,
                "action":     row.AuditLog.action,
                "resource":   row.AuditLog.resource,
                "detail":     row.AuditLog.detail,
                "created_at": row.AuditLog.created_at.isoformat(),
            }
            for row in rows
        ],
        "total":    total,
        "page":     page,
        "per_page": per_page,
        "pages":    (total + per_page - 1) // per_page,
    }