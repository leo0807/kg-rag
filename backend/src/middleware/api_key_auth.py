"""
H7.2 API Key 认证中间件
X-API-Key 头 → 校验 hash / 作用域 / IP 白名单 / 限流 / 记录使用
"""
from __future__ import annotations

import hashlib
import logging
import time
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# 只对 /api/v1/ 路径启用 API Key 认证
_V1_PREFIX = "/api/v1/"

# 不需要 API Key 的公开路径
_PUBLIC_PATHS = {"/api/v1/docs", "/api/v1/openapi.json"}


def _hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _check_ip(allowed_ips: list, client_ip: str) -> bool:
    if not allowed_ips:
        return True
    return client_ip in allowed_ips


class ApiKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        if not path.startswith(_V1_PREFIX) or path in _PUBLIC_PATHS:
            return await call_next(request)

        api_key = request.headers.get("X-API-Key", "")
        if not api_key:
            return JSONResponse(status_code=401, content={"error": "缺少 X-API-Key 头"})

        key_obj = await self._resolve_key(api_key)
        if key_obj is None:
            return JSONResponse(status_code=401, content={"error": "API Key 无效或已停用"})

        # IP 白名单
        client_ip = request.client.host if request.client else ""
        if not _check_ip(key_obj.get("allowed_ips", []), client_ip):
            return JSONResponse(status_code=403, content={"error": "IP 不在白名单"})

        # 作用域检查（路径→scope 映射）
        required_scope = _infer_scope(request.method, path)
        scopes: list = key_obj.get("scopes", [])
        if required_scope and scopes and required_scope not in scopes:
            return JSONResponse(status_code=403, content={"error": f"缺少 scope: {required_scope}"})

        # 注入上下文
        request.state.api_key_id  = key_obj["id"]
        request.state.tenant_id   = key_obj.get("tenant_id")
        request.state.api_key_obj = key_obj

        start = time.monotonic()
        response = await call_next(request)
        duration_ms = int((time.monotonic() - start) * 1000)

        # 异步记录使用
        import asyncio
        asyncio.create_task(self._record_usage(
            key_obj["id"], path, response.status_code, duration_ms, client_ip
        ))

        return response

    async def _resolve_key(self, raw_key: str) -> dict | None:
        """从数据库查找并校验 API Key。"""
        try:
            from ..db.integration_models import ApiKey
            from ..db.session import AsyncSessionLocal
            from sqlalchemy import select
            from datetime import datetime

            key_hash = _hash_key(raw_key)
            async with AsyncSessionLocal() as db:
                obj = (await db.execute(
                    select(ApiKey).where(
                        ApiKey.key_hash == key_hash,
                        ApiKey.is_active == True,
                    )
                )).scalar_one_or_none()
                if obj is None:
                    return None
                if obj.expires_at and obj.expires_at < datetime.utcnow():
                    return None
                return {
                    "id": obj.id, "tenant_id": obj.tenant_id,
                    "scopes": obj.scopes or [], "allowed_ips": obj.allowed_ips or [],
                    "rate_limit": obj.rate_limit,
                }
        except Exception as e:
            logger.warning("api key resolve error: %s", e)
            return None

    async def _record_usage(
        self, key_id: str, endpoint: str, status: int, duration_ms: int, ip: str
    ) -> None:
        try:
            from ..db.integration_models import ApiKeyUsage
            from ..db.session import AsyncSessionLocal
            async with AsyncSessionLocal() as db:
                db.add(ApiKeyUsage(
                    api_key_id=key_id, endpoint=endpoint,
                    status_code=status, duration_ms=duration_ms, ip_address=ip,
                ))
                await db.commit()
        except Exception as e:
            logger.debug("api key usage record error: %s", e)


def _infer_scope(method: str, path: str) -> str:
    """根据请求路径推断所需 scope。"""
    if "query" in path:
        return "query:read"
    if "feedback" in path:
        return "feedback:write"
    if "documents" in path:
        return "documents:read"
    return ""
