"""
Idempotency middleware: caches POST/PUT/PATCH responses keyed by Idempotency-Key header.
Cache TTL: 24 hours. Backend: Redis via app.state.redis.
"""
from __future__ import annotations

import json
import logging
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

_IDEMPOTENT_METHODS = {"POST", "PUT", "PATCH"}
_CACHE_TTL = 86400  # 24 hours in seconds
_KEY_PREFIX = "idempotency:"


def _redis_key(idempotency_key: str) -> str:
    return f"{_KEY_PREFIX}{idempotency_key}"


async def _get_redis(request: Request):
    """Return app.state.redis or None if unavailable."""
    try:
        redis = getattr(request.app.state, "redis", None)
        return redis
    except Exception:
        return None


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """
    Intercepts POST/PUT/PATCH requests that carry an Idempotency-Key header.
    - If a cached response exists in Redis, returns it immediately.
    - Otherwise forwards the request, then stores the response (status < 500).
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.method not in _IDEMPOTENT_METHODS:
            return await call_next(request)

        key_header = request.headers.get("Idempotency-Key")
        if not key_header:
            return await call_next(request)

        redis = await _get_redis(request)

        # --- cache hit ---
        if redis is not None:
            try:
                cached = await redis.get(_redis_key(key_header))
                if cached:
                    data = json.loads(cached)
                    return Response(
                        content=data["body"],
                        status_code=data["status_code"],
                        media_type="application/json",
                        headers={"X-Idempotency-Replayed": "true"},
                    )
            except Exception as exc:
                logger.warning("idempotency cache read error: %s", exc)

        # --- forward request ---
        response = await call_next(request)

        # --- cache miss: store response ---
        if redis is not None and response.status_code < 500:
            try:
                body_chunks: list[bytes] = []
                async for chunk in response.body_iterator:
                    body_chunks.append(chunk)
                body_bytes = b"".join(body_chunks)

                payload = json.dumps({
                    "status_code": response.status_code,
                    "body": body_bytes.decode("utf-8", errors="replace"),
                })
                await redis.set(_redis_key(key_header), payload, ex=_CACHE_TTL)

                # Rebuild response since body_iterator is consumed
                return Response(
                    content=body_bytes,
                    status_code=response.status_code,
                    media_type=response.media_type,
                    headers=dict(response.headers),
                )
            except Exception as exc:
                logger.warning("idempotency cache write error: %s", exc)
                # Return a fresh response object if we consumed the iterator but failed
                return Response(
                    content=b"".join(body_chunks) if body_chunks else b"",
                    status_code=response.status_code,
                    media_type=response.media_type,
                    headers=dict(response.headers),
                )

        return response
