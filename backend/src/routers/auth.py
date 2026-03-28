"""
src/routers/auth.py
用户注册、登录接口
"""
import uuid
import logging
import re
from pydantic import BaseModel, field_validator
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from ..db.session import get_db
from ..db.models import User, AuditLog
from ..auth.password import hash_password, verify_password
from ..auth.jwt import create_access_token
from ..auth.deps import get_current_user, get_admin_user


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    username:   str
    email:      str
    password:   str
    full_name:  str = ""
    department: str = ""

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


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    user_id:      str
    username:     str
    full_name:    str
    department:   str
    is_admin:     bool

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


@router.post("/register", response_model=TokenResponse)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    # 检查用户名是否已存在
    result = await db.execute(
        select(User).where(User.username == req.username)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已存在",
        )

    # 第一个注册的用户自动成为管理员
    count_result = await db.execute(select(User))
    is_first     = len(count_result.scalars().all()) == 0

    user = User(
        id         = str(uuid.uuid4()),
        username   = req.username,
        email      = req.email,
        hashed_pw  = hash_password(req.password),
        full_name  = req.full_name,
        department = req.department,
        is_admin   = is_first,
    )
    db.add(user)

    log = AuditLog(
        user_id  = user.id,
        action   = "register",
        resource = "user",
        detail   = f"用户 {req.username} 注册",
    )
    db.add(log)
    await db.commit()

    token = create_access_token(user.id, user.is_admin)
    logger.info("用户注册成功 username=%s is_admin=%s", user.username, user.is_admin)

    return TokenResponse(
        access_token = token,
        user_id      = user.id,
        username     = user.username,
        full_name    = user.full_name,
        department   = user.department,
        is_admin     = user.is_admin,
    )


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User).where(User.username == req.username)
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(req.password, user.hashed_pw):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号已被禁用",
        )

    log = AuditLog(
        user_id  = user.id,
        action   = "login",
        resource = "user",
        detail   = f"用户 {user.username} 登录",
    )
    db.add(log)
    await db.commit()

    token = create_access_token(user.id, user.is_admin)
    return TokenResponse(
        access_token = token,
        user_id      = user.id,
        username     = user.username,
        full_name    = user.full_name,
        department   = user.department,
        is_admin     = user.is_admin,
    )

@router.put("/password")
async def change_password(
    req:  ChangePasswordRequest,
    db:   AsyncSession = Depends(get_db),
    user: User         = Depends(get_current_user),
):
    if not verify_password(req.old_password, user.hashed_pw):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="原密码错误",
        )

    user.hashed_pw = hash_password(req.new_password)

    log = AuditLog(
        user_id  = user.id,
        action   = "change_password",
        resource = "user",
        detail   = f"用户 {user.username} 修改了密码",
    )
    db.add(log)
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
        # 检查邮箱是否已被使用
        result = await db.execute(
            select(User).where(User.email == req.email, User.id != user.id)
        )
        if result.scalar_one_or_none():
            raise HTTPException(400, "邮箱已被其他用户使用")
        user.email = req.email

    log = AuditLog(
        user_id  = user.id,
        action   = "update_profile",
        resource = "user",
        detail   = f"用户 {user.username} 更新了个人资料",
    )
    db.add(log)
    await db.commit()

    return {
        "status":     "OK",
        "username":   user.username,
        "full_name":  user.full_name,
        "department": user.department,
        "email":      user.email,
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

@router.get("/users")
async def list_users(
    db:   AsyncSession = Depends(get_db),
    user: User         = Depends(get_admin_user),
):
    """获取所有用户列表（仅管理员）"""
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


@router.put("/users/{user_id}/toggle")
async def toggle_user(
    user_id: str,
    db:      AsyncSession = Depends(get_db),
    admin:   User         = Depends(get_admin_user),
):
    """启用/禁用用户（仅管理员）"""
    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()

    if not target:
        raise HTTPException(404, "用户不存在")

    if target.id == admin.id:
        raise HTTPException(400, "不能禁用自己")

    target.is_active = not target.is_active

    log = AuditLog(
        user_id  = admin.id,
        action   = "toggle_user",
        resource = "user",
        detail   = f"管理员 {admin.username} {'启用' if target.is_active else '禁用'}了用户 {target.username}",
    )
    db.add(log)
    await db.commit()

    return {
        "status":    "OK",
        "user_id":   target.id,
        "username":  target.username,
        "is_active": target.is_active,
    }


@router.put("/users/{user_id}/admin")
async def toggle_admin(
    user_id: str,
    db:      AsyncSession = Depends(get_db),
    admin:   User         = Depends(get_admin_user),
):
    """设置/取消管理员权限（仅管理员）"""
    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()

    if not target:
        raise HTTPException(404, "用户不存在")

    if target.id == admin.id:
        raise HTTPException(400, "不能修改自己的管理员权限")

    target.is_admin = not target.is_admin

    log = AuditLog(
        user_id  = admin.id,
        action   = "toggle_admin",
        resource = "user",
        detail   = f"管理员 {admin.username} {'授予' if target.is_admin else '撤销'}了用户 {target.username} 的管理员权限",
    )
    db.add(log)
    await db.commit()

    return {
        "status":   "OK",
        "user_id":  target.id,
        "username": target.username,
        "is_admin": target.is_admin,
    }

@router.get("/me")
async def me(db: AsyncSession = Depends(get_db)):
    """临时接口，测试用"""
    result = await db.execute(select(User))
    users  = result.scalars().all()
    return [{"id": u.id, "username": u.username, "is_admin": u.is_admin} for u in users]

