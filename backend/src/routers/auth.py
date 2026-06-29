"""
src/routers/auth.py
用户注册、登录接口
"""
import uuid
import logging
import re
from datetime import datetime, timezone
from pydantic import BaseModel, field_validator
from fastapi import APIRouter, Depends, HTTPException, status, Body
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

    token = create_access_token(user.id, user.is_admin, tenant_id=user.tenant_id)
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

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    if not verify_password(req.password, user.hashed_pw):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="密码错误，请重试",
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

    token = create_access_token(user.id, user.is_admin, tenant_id=user.tenant_id)
    return TokenResponse(
        access_token = token,
        user_id      = user.id,
        username     = user.username,
        full_name    = user.full_name,
        department   = user.department,
        is_admin     = user.is_admin,
    )

_PW_RESET_TTL = 86400  # 24 小时（秒）


@router.post("/forgot-password")
async def forgot_password(
    username: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
):
    """
    密码重置申请：向管理员发送通知邮件/Webhook。
    同一用户 24 小时内只发送一次；超时未处理后允许重新发起。
    """
    # 1. 验证用户存在
    user = (await db.execute(select(User).where(User.username == username))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在，请确认工号")

    # 2. Redis 限速检查（24h 内只允许一次）
    try:
        from ..services.infra.cache import get_redis
        r = get_redis()
        rate_key = f"pw_reset_req:{username}"
        ttl = r.ttl(rate_key)
        if ttl > 0:
            h, m = ttl // 3600, (ttl % 3600) // 60
            raise HTTPException(
                status_code=429,
                detail=f"申请已提交，管理员处理中。距可重新申请还有 {h} 小时 {m} 分钟",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("Redis 限速检查失败，跳过: %s", e)
        r = None
        rate_key = None

    # 3. 获取所有管理员邮箱
    admins = (await db.execute(select(User).where(User.is_admin == True))).scalars().all()
    admin_emails = [a.email for a in admins if a.email and "@" in a.email]

    # 4. 发送通知（邮件 + Webhook 双通道）
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    body = (
        f"用户密码重置申请\n\n"
        f"工号：{user.username}\n"
        f"姓名：{user.full_name or '—'}\n"
        f"部门：{user.department or '—'}\n"
        f"申请时间：{now_str}\n\n"
        f"请登录后台 → 用户管理 → 找到该用户 → 执行密码重置操作。"
    )
    try:
        from ..services.monitoring.alert_sender import alert_sender
        for email in admin_emails:
            await alert_sender.send_email(
                to=email,
                subject=f"[CPS知识库] 密码重置申请 · 工号 {user.username}",
                body=body,
            )
        # Webhook 作为备用通知渠道
        await alert_sender.send_dingtalk(
            f"📌 **密码重置申请**\n工号：{user.username}  姓名：{user.full_name or '—'}\n{now_str}",
            level="warning",
        )
    except Exception as e:
        logger.warning("重置申请通知发送失败: %s", e)

    # 5. 写入 Redis 限速键（24h TTL）
    try:
        if r is not None and rate_key:
            r.setex(rate_key, _PW_RESET_TTL, "1")
    except Exception as e:
        logger.warning("Redis 限速键写入失败: %s", e)

    logger.info("密码重置申请 username=%s emails=%s", username, admin_emails)
    return {"detail": "申请已发送，请等待管理员处理（通常 1 个工作日内）"}


# 密码修改、个人资料、token 刷新已迁移至 auth_profile.py
# 原有路由由 auth_profile_router 提供，与此模块共享 /api/auth 前缀
