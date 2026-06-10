"""
G2.1 租户识别中间件
识别顺序：JWT tenant_id → X-Tenant-Slug 头 → 子域名
"""
from __future__ import annotations

import logging
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from ..auth.jwt import decode_token
from ..db.session import AsyncSessionLocal
from ..db.tenant_models import Tenant

logger = logging.getLogger(__name__)

# 不需要租户上下文的路径前缀
_PUBLIC_PATHS = {
    "/api/auth/login",
    "/api/auth/register",
    "/api/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/uploads",
    "/api/shared",
}

# 需要跳过的前缀（streaming、静态资源等）
_SKIP_PREFIXES = ("/favicon", "/uploads/")


def _is_public(path: str) -> bool:
    if any(path.startswith(p) for p in _SKIP_PREFIXES):
        return True
    for pub in _PUBLIC_PATHS:
        if path.startswith(pub):
            return True
    return False


def _extract_tenant_id_from_jwt(request: Request) -> str | None:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    try:
        payload = decode_token(auth[7:])
        return payload.get("tenant_id")
    except Exception:
        return None


def _extract_slug_from_subdomain(request: Request) -> str | None:
    host = request.headers.get("host", "")
    parts = host.split(".")
    # acme.kgrag.com → parts[0] = "acme"
    if len(parts) >= 3 and parts[0] not in ("www", "api", "app"):
        return parts[0]
    return None


async def _load_tenant_by_id(tenant_id: str) -> Tenant | None:
    from sqlalchemy import select
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
        return result.scalar_one_or_none()


async def _load_tenant_by_slug(slug: str) -> Tenant | None:
    from sqlalchemy import select
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Tenant).where(Tenant.slug == slug))
        return result.scalar_one_or_none()


class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path

        if _is_public(path):
            return await call_next(request)

        tenant: Tenant | None = None

        # 1. JWT 中的 tenant_id
        tid = _extract_tenant_id_from_jwt(request)
        if tid:
            tenant = await _load_tenant_by_id(tid)

        # 2. X-Tenant-Slug 头
        if tenant is None:
            slug = request.headers.get("X-Tenant-Slug")
            if slug:
                tenant = await _load_tenant_by_slug(slug)

        # 3. 子域名
        if tenant is None:
            subdomain_slug = _extract_slug_from_subdomain(request)
            if subdomain_slug:
                tenant = await _load_tenant_by_slug(subdomain_slug)

        # 无租户上下文 — 平台级 API 或未认证请求放行（由路由层鉴权）
        if tenant is None:
            return await call_next(request)

        if tenant.status != "active":
            return JSONResponse(
                status_code=403,
                content={"error": f"租户状态异常: {tenant.status}"},
            )

        request.state.tenant = tenant
        request.state.tenant_id = tenant.id
        return await call_next(request)
