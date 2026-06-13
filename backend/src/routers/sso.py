"""
H5.3 SSO 登录流程
GET  /api/auth/sso/login    — 重定向到 IdP
GET  /api/auth/sso/callback — IdP 回调，换取本系统 JWT
POST /api/auth/sso/logout   — 登出（清理本地会话）
"""
from __future__ import annotations

import logging
import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.jwt import create_access_token
from ..db.models import User
from ..db.session import get_db
from ..db.tenant_models import Tenant
from ..services.auth.oidc_provider import OIDCError, build_oidc_from_tenant
from ..services.multitenant.tenant_filter import get_tenant_id_optional

router = APIRouter(prefix="/api/auth/sso", tags=["sso"])
logger = logging.getLogger(__name__)

# 简单内存 state 存储（生产环境应用 Redis）
_states: dict[str, str] = {}   # state → tenant_id


async def _get_tenant(db: AsyncSession, tenant_id: str) -> Tenant | None:
    return (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()


@router.get("/login")
async def sso_login(
    request: Request,
    tenant_slug: str = Query(..., description="租户 slug"),
    db: AsyncSession = Depends(get_db),
):
    """重定向到租户配置的 IdP 登录页面。"""
    tenant = (await db.execute(
        select(Tenant).where(Tenant.slug == tenant_slug)
    )).scalar_one_or_none()
    if not tenant:
        raise HTTPException(404, "租户不存在")

    provider = build_oidc_from_tenant(tenant.settings or {})
    if not provider:
        raise HTTPException(400, "该租户未配置 OIDC SSO")

    state = secrets.token_urlsafe(24)
    _states[state] = tenant.id

    try:
        auth_url = await provider.get_authorization_url(state)
    except Exception as e:
        raise HTTPException(500, f"获取授权 URL 失败: {e}")

    return RedirectResponse(auth_url)


@router.get("/callback")
async def sso_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """IdP 回调：code → 本系统 JWT。"""
    tenant_id = _states.pop(state, None)
    if not tenant_id:
        raise HTTPException(400, "无效的 state 参数")

    tenant = await _get_tenant(db, tenant_id)
    if not tenant:
        raise HTTPException(404, "租户不存在")

    provider = build_oidc_from_tenant(tenant.settings or {})
    if not provider:
        raise HTTPException(500, "SSO 配置丢失")

    try:
        token_data = await provider.exchange_code_for_token(code)
        user_info  = await provider.get_user_info(token_data["access_token"])
    except OIDCError as e:
        raise HTTPException(400, str(e))

    email    = user_info.get("email") or ""
    username = email.split("@")[0] if email else f"sso_{uuid.uuid4().hex[:8]}"
    name     = user_info.get("name") or username

    # 查找或创建用户
    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if not user:
        user = User(
            id=str(uuid.uuid4()), username=username[:6],
            email=email, hashed_pw="__sso__",
            full_name=name, tenant_id=tenant_id,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    access_token = create_access_token(user.id, user.is_admin, tenant_id=user.tenant_id)
    return JSONResponse({
        "access_token": access_token,
        "token_type": "bearer",
        "user": {"id": user.id, "email": email, "name": name},
    })


@router.post("/logout")
async def sso_logout():
    """本地登出（前端清除 token 即可；IdP 全局登出需扩展）。"""
    return {"ok": True, "message": "已登出，请清除本地 token"}
