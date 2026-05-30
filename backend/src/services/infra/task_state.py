"""
Unified task state store abstraction.

Provides a Redis-backed (and in-memory test) store for long-running
background task state. Replaces per-service process-local _tasks dicts.

Key format: {namespace}:{task_id}
  eval:objective:{task_id}
  eval:faithfulness:{task_id}
  eval:dataset:{task_id}
  eval:retrieval:{task_id}
  eval:ab:{task_id}
  scan:conflict:{scan_id}

TTL defaults to 7 days (matching Celery result_expires in celery_app.py).
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

DEFAULT_TTL = 86400 * 7  # 7 days


@dataclass
class TaskState:
    """Task state snapshot.

    Business-specific counters/fields go in `progress`.
    Large result payloads go in `result`.
    Caller-supplied context (user_id, etc.) goes in `metadata`.
    """

    task_id: str
    status: str  # queued / running / done / failed / cancelled
    progress: dict[str, Any] = field(default_factory=dict)
    result: Any = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float | None = None
    updated_at: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskState":
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})


class TaskStateStore(Protocol):
    """Task state storage abstraction (sync interface)."""

    def set(self, key: str, state: TaskState, ttl_seconds: int = DEFAULT_TTL) -> None: ...
    def get(self, key: str) -> TaskState | None: ...
    def update(self, key: str, refresh_ttl: bool = False, **fields: Any) -> TaskState | None: ...
    def delete(self, key: str) -> None: ...
    def list_by_prefix(self, prefix: str, limit: int = 100) -> list[TaskState]: ...


class RedisTaskStateStore:
    """Redis-backed implementation. Thread-safe for use in Celery workers."""

    def __init__(self, redis_url: str | None = None) -> None:
        import redis as _redis
        from ...core.config import settings

        url = redis_url or settings.REDIS_URL
        self._r = _redis.from_url(url, decode_responses=True)

    def set(self, key: str, state: TaskState, ttl_seconds: int = DEFAULT_TTL) -> None:
        now = time.time()
        if state.created_at is None:
            state.created_at = now
        state.updated_at = now
        self._r.setex(key, ttl_seconds, json.dumps(state.to_dict(), ensure_ascii=False))

    def get(self, key: str) -> TaskState | None:
        raw = self._r.get(key)
        if not raw:
            return None
        return TaskState.from_dict(json.loads(raw))

    def update(self, key: str, refresh_ttl: bool = False, **fields: Any) -> TaskState | None:
        state = self.get(key)
        if state is None:
            return None
        for k, v in fields.items():
            if hasattr(state, k):
                setattr(state, k, v)
        if refresh_ttl:
            ttl = DEFAULT_TTL
        else:
            ttl = self._r.ttl(key)
            ttl = ttl if ttl > 0 else DEFAULT_TTL
        self.set(key, state, ttl_seconds=ttl)
        return state

    def delete(self, key: str) -> None:
        self._r.delete(key)

    def list_by_prefix(self, prefix: str, limit: int = 100) -> list[TaskState]:
        keys: list[str] = []
        for key in self._r.scan_iter(match=f"{prefix}*", count=200):
            keys.append(key)
            if len(keys) >= limit:
                break
        states: list[TaskState] = []
        for key in keys:
            s = self.get(key)
            if s:
                states.append(s)
        return sorted(
            states,
            key=lambda s: s.updated_at or s.created_at or 0.0,
            reverse=True,
        )


class InMemoryTaskStateStore:
    """In-memory implementation for unit tests."""

    def __init__(self) -> None:
        self._data: dict[str, TaskState] = {}

    def set(self, key: str, state: TaskState, ttl_seconds: int = DEFAULT_TTL) -> None:
        now = time.time()
        if state.created_at is None:
            state.created_at = now
        state.updated_at = now
        # store a copy so external mutations don't affect stored state
        self._data[key] = TaskState.from_dict(state.to_dict())

    def get(self, key: str) -> TaskState | None:
        s = self._data.get(key)
        if s is None:
            return None
        return TaskState.from_dict(s.to_dict())

    def update(self, key: str, refresh_ttl: bool = False, **fields: Any) -> TaskState | None:  # noqa: ARG002
        s = self._data.get(key)
        if s is None:
            return None
        for k, v in fields.items():
            if hasattr(s, k):
                setattr(s, k, v)
        s.updated_at = time.time()
        return TaskState.from_dict(s.to_dict())

    def delete(self, key: str) -> None:
        self._data.pop(key, None)

    def list_by_prefix(self, prefix: str, limit: int = 100) -> list[TaskState]:
        results = [
            TaskState.from_dict(s.to_dict())
            for k, s in self._data.items()
            if k.startswith(prefix)
        ][:limit]
        return sorted(
            results,
            key=lambda s: s.updated_at or s.created_at or 0.0,
            reverse=True,
        )


_global_store: RedisTaskStateStore | None = None


def get_task_state_store() -> RedisTaskStateStore:
    """Return the process-global Redis store (lazy-initialized)."""
    global _global_store
    if _global_store is None:
        _global_store = RedisTaskStateStore()
    return _global_store
