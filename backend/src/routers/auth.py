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


@router.get("/me")
async def me(db: AsyncSession = Depends(get_db)):
    """临时接口，测试用"""
    result = await db.execute(select(User))
    users  = result.scalars().all()
    return [{"id": u.id, "username": u.username, "is_admin": u.is_admin} for u in users]