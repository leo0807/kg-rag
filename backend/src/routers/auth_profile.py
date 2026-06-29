"""
src/routers/auth_profile.py
已登录用户的密码修改、个人资料更新、token 刷新接口。
（从 auth.py 拆分出来以保持单文件 < 300 行规范）
"""
import logging
from pydantic import BaseModel, field_validator
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..db.session import get_db
from ..db.models import User, AuditLog
from ..auth.password import hash_password, verify_password
from ..auth.jwt import create_access_token
from ..auth.deps import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("新密码至少6位")
        return v


class UpdateProfileRequest(BaseModel):
    full_name:  str = ""
    department: str = ""
    email:      str = ""


@router.put("/password")
async def change_password(
    req:  ChangePasswordRequest,
    db:   AsyncSession = Depends(get_db),
    user: User         = Depends(get_current_user),
):
    if not verify_password(req.old_password, user.hashed_pw):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="原密码错误")

    user.hashed_pw = hash_password(req.new_password)
    db.add(AuditLog(
        user_id=user.id, action="change_password", resource="user",
        detail=f"用户 {user.username} 修改了密码",
    ))
    await db.commit()
    return {"status": "OK", "message": "密码修改成功"}


@router.put("/profile")
async def update_profile(
    req:  UpdateProfileRequest,
    db:   AsyncSession = Depends(get_db),
    user: User         = Depends(get_current_user),
):
    if req.full_name:
        user.full_name = req.full_name
    if req.department:
        user.department = req.department
    if req.email:
        if (await db.execute(select(User).where(User.email == req.email, User.id != user.id))).scalar_one_or_none():
            raise HTTPException(400, "邮箱已被其他用户使用")
        user.email = req.email

    db.add(AuditLog(
        user_id=user.id, action="update_profile", resource="user",
        detail=f"用户 {user.username} 更新了个人资料",
    ))
    await db.commit()
    return {
        "status": "OK", "username": user.username,
        "full_name": user.full_name, "department": user.department, "email": user.email,
    }


@router.get("/profile")
async def get_profile(
    db:   AsyncSession = Depends(get_db),
    user: User         = Depends(get_current_user),
):
    return {
        "user_id":    user.id,
        "username":   user.username,
        "full_name":  user.full_name,
        "department": user.department,
        "email":      user.email,
        "is_admin":   user.is_admin,
        "created_at": user.created_at.isoformat(),
    }


@router.post("/refresh")
async def refresh_token(
    db:   AsyncSession = Depends(get_db),
    user: User         = Depends(get_current_user),
):
    """刷新 token，返回新 token"""
    new_token = create_access_token(user.id, user.is_admin, tenant_id=user.tenant_id)
    db.add(AuditLog(
        user_id=user.id, action="refresh_token", resource="auth",
        detail=f"用户 {user.username} 刷新了 token",
    ))
    await db.commit()
    return {"access_token": new_token, "token_type": "bearer"}
