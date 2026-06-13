"""
FastAPI 依赖注入：从请求头提取当前用户
"""
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from neo4j import Driver
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from .jwt import decode_token
from ..core.database import get_driver
from ..db.session import get_db
from ..db.models import User

bearer = HTTPBearer(auto_error=False)
bearer_optional = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少认证凭证",
        )
    try:
        payload = decode_token(credentials.credentials)
        user_id = payload["sub"]
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭证",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user   = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在或已禁用",
        )
    return user


async def get_admin_user(
    current_user: User = Depends(get_current_user),
) -> User:
    if not (current_user.is_admin or current_user.is_platform_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限",
        )
    return current_user


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_optional),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """尝试从请求头中提取用户，无 Token 时返回 None（不报错）"""
    if not credentials:
        return None
    try:
        payload = decode_token(credentials.credentials)
        user_id = payload["sub"]
    except Exception:
        return None
    result = await db.execute(select(User).where(User.id == user_id))
    user   = result.scalar_one_or_none()
    return user if (user and user.is_active) else None


def get_protected_driver(_: User = Depends(get_current_user)) -> Driver:
    return get_driver()


def get_admin_driver(_: User = Depends(get_admin_user)) -> Driver:
    return get_driver()
