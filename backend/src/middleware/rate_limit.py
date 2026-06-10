"""
G4.3 基于 Redis 滑动窗口的速率限制中间件
"""
from __future__ import annotations

import logging
import time
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# 不需要限流的路径前缀
_SKIP_PREFIXES = (
    "/api/health", "/api/auth/login", "/api/auth/register",
    "/docs", "/redoc", "/openapi.json", "/uploads/",
)


def _should_skip(path: str) -> bool:
    return any(path.startswith(p) for p in _SKIP_PREFIXES)


class RateLimiter:
    """基于 Redis 的双窗口限流器（分钟级 + 小时级）。"""

    def __init__(self, redis_client=None):
        self._redis = redis_client

    async def _get_redis(self):
        if self._redis is not None:
            return self._redis
        try:
            import redis.asyncio as aioredis
            from ...core.config import settings
            self._redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        except Exception:
            self._redis = None
        return self._redis

    async def check(
        self,
        tenant_id: str,
        limit_per_minute: int = 60,
        limit_per_hour: int = 1000,
    ) -> tuple[bool, int]:
        """返回 (allowed, retry_after_seconds)。"""
        redis = await self._get_redis()
        if redis is None:
            return True, 0   # Redis 不可用时放行

        now = int(time.time())
        minute_slot = now // 60
        hour_slot   = now // 3600

        minute_key = f"rl:{tenant_id}:m:{minute_slot}"
        hour_key   = f"rl:{tenant_id}:h:{hour_slot}"

        try:
            pipe = redis.pipeline()
            pipe.incr(minute_key)
            pipe.expire(minute_key, 120)
            pipe.incr(hour_key)
            pipe.expire(hour_key, 7200)
            results = await pipe.execute()

            m_count, _, h_count, _ = results

            if m_count > limit_per_minute:
                return False, 60 - (now % 60)
            if h_count > limit_per_hour:
                return False, 3600 - (now % 3600)
        except Exception as exc:
            logger.warning("rate limiter redis error: %s", exc)
            return True, 0

        return True, 0


_limiter = RateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if _should_skip(request.url.path):
            return await call_next(request)

        tenant_id = getattr(request.state, "tenant_id", None)
        if not tenant_id:
            return await call_next(request)

        # 从数据库加载租户配额（简化：使用默认值，避免每请求查询DB）
        allowed, retry_after = await _limiter.check(tenant_id)
        if not allowed:
            return JSONResponse(
                status_code=429,
                headers={"Retry-After": str(retry_after)},
                content={"error": "请求过于频繁，请稍后重试", "retry_after": retry_after},
            )

        return await call_next(request)
