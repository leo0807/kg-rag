from __future__ import annotations

import logging
import threading
import time
import uuid
from collections import deque
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.jwt import decode_token
from ...db.models import User
from ...services.infra.cache import get_redis

logger = logging.getLogger(__name__)

ACTIVE_WINDOW_SECONDS = 120
REQUEST_WINDOW_SECONDS = 60
_USER_ZSET_KEY = "ops:presence:users"
_REQUEST_ZSET_KEY = "ops:presence:requests"

_memory_lock = threading.Lock()
_memory_users: dict[str, float] = {}
_memory_requests: deque[float] = deque()


def _extract_bearer_token(auth_header: str) -> str:
    if not auth_header:
        return ""
    scheme, _, token = auth_header.partition(" ")
    if scheme.lower() != "bearer":
        return ""
    return token.strip()


def _trim_memory(now_ts: float) -> None:
    user_cutoff = now_ts - ACTIVE_WINDOW_SECONDS
    request_cutoff = now_ts - REQUEST_WINDOW_SECONDS
    stale_users = [user_id for user_id, ts in _memory_users.items() if ts < user_cutoff]
    for user_id in stale_users:
        _memory_users.pop(user_id, None)
    while _memory_requests and _memory_requests[0] < request_cutoff:
        _memory_requests.popleft()


def track_request_activity(auth_header: str, path: str) -> None:
    if not path.startswith("/api/"):
        return
    if path.startswith("/api/health") or path.startswith("/api/auth/login"):
        return

    now_ts = time.time()
    token = _extract_bearer_token(auth_header)
    user_id = ""
    if token:
        try:
            payload = decode_token(token)
            user_id = str(payload.get("sub") or "")
        except Exception:
            user_id = ""

    try:
        redis_client = get_redis()
        pipe = redis_client.pipeline()
        pipe.zadd(_REQUEST_ZSET_KEY, {f"{now_ts:.6f}:{uuid.uuid4().hex}": now_ts})
        pipe.zremrangebyscore(_REQUEST_ZSET_KEY, 0, now_ts - REQUEST_WINDOW_SECONDS)
        if user_id:
            pipe.zadd(_USER_ZSET_KEY, {user_id: now_ts})
            pipe.zremrangebyscore(_USER_ZSET_KEY, 0, now_ts - ACTIVE_WINDOW_SECONDS)
        pipe.execute()
        return
    except Exception as exc:
        logger.debug("presence redis fallback: %s", exc)

    with _memory_lock:
        _memory_requests.append(now_ts)
        if user_id:
            _memory_users[user_id] = now_ts
        _trim_memory(now_ts)


def _load_active_users_from_memory(limit: int) -> list[tuple[str, float]]:
    now_ts = time.time()
    with _memory_lock:
        _trim_memory(now_ts)
        items = sorted(_memory_users.items(), key=lambda item: item[1], reverse=True)
        return items[: max(limit, 1)]


def _count_recent_requests_from_memory() -> int:
    now_ts = time.time()
    with _memory_lock:
        _trim_memory(now_ts)
        return len(_memory_requests)


async def get_presence_snapshot(
    db: AsyncSession,
    *,
    user_limit: int = 6,
) -> dict[str, Any]:
    active_pairs: list[tuple[str, float]] = []
    active_user_count = 0
    requests_1m = 0
    now_ts = time.time()
    try:
        redis_client = get_redis()
        user_cutoff = now_ts - ACTIVE_WINDOW_SECONDS
        request_cutoff = now_ts - REQUEST_WINDOW_SECONDS
        active_user_count = int(redis_client.zcount(_USER_ZSET_KEY, user_cutoff, "+inf") or 0)
        active_pairs = [
            (str(user_id), float(score))
            for user_id, score in redis_client.zrevrangebyscore(
                _USER_ZSET_KEY,
                "+inf",
                user_cutoff,
                start=0,
                num=max(user_limit, 1),
                withscores=True,
            )
        ]
        requests_1m = int(
            redis_client.zcount(_REQUEST_ZSET_KEY, request_cutoff, "+inf") or 0
        )
    except Exception as exc:
        logger.debug("presence snapshot memory fallback: %s", exc)
        active_pairs = _load_active_users_from_memory(user_limit)
        with _memory_lock:
            _trim_memory(now_ts)
            active_user_count = len(_memory_users)
        requests_1m = _count_recent_requests_from_memory()

    user_ids = [user_id for user_id, _ in active_pairs]
    user_rows = {}
    if user_ids:
        result = await db.execute(
            select(User.id, User.username, User.full_name).where(User.id.in_(user_ids))
        )
        user_rows = {
            row.id: {"username": row.username, "full_name": row.full_name or ""}
            for row in result.all()
        }

    users = []
    for user_id, last_seen in active_pairs:
        profile = user_rows.get(user_id, {})
        users.append(
            {
                "user_id": user_id,
                "username": profile.get("username", user_id[:8]),
                "full_name": profile.get("full_name", ""),
                "last_seen": int(last_seen),
            }
        )

    return {
        "active_users": active_user_count,
        "requests_1m": requests_1m,
        "active_window_seconds": ACTIVE_WINDOW_SECONDS,
        "users": users,
    }
