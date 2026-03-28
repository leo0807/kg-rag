"""
src/routers/users.py
管理员用户管理、审计日志
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from ..db.session import get_db
from ..db.models import User, AuditLog
from ..auth.deps import get_admin_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/users", tags=["users"])


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