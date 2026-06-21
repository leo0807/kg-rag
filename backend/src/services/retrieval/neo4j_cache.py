"""
Neo4j 查询缓存层（可选包装）。

用法（默认不启用，不影响现有查询路径）::

    from src.services.retrieval.neo4j_cache import cached_session

    with cached_session(driver, ttl=60) as session:
        result = session.run("MATCH (d:Document) RETURN d.name LIMIT 10")

若 ENABLE_NEO4J_QUERY_CACHE 环境变量未设置或为 false，则 cached_session
直接返回原生 driver.session()，零性能开销、零行为变更。

缓存策略
--------
- Key: sha256(cypher + sorted(params))
- 存储: 进程内 dict（LRU，最多 MAX_ENTRIES 条）
- TTL: 每条目独立，到期后下次访问时惰性淘汰
- 线程安全: 用 threading.Lock 保护写操作
- 不缓存: 含 CREATE/MERGE/SET/DELETE/DETACH 的写查询
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import os
import threading
import time
from typing import Any, Generator

from neo4j import Driver

logger = logging.getLogger(__name__)

_CACHE_ENABLED = os.getenv("ENABLE_NEO4J_QUERY_CACHE", "false").lower() in ("1", "true", "yes")
MAX_ENTRIES = int(os.getenv("NEO4J_CACHE_MAX_ENTRIES", "256"))
DEFAULT_TTL = int(os.getenv("NEO4J_CACHE_TTL_SECONDS", "60"))

_WRITE_KEYWORDS = frozenset({"CREATE", "MERGE", "SET", "DELETE", "DETACH", "REMOVE", "DROP"})


def _is_write_query(cypher: str) -> bool:
    upper = cypher.upper()
    return any(kw in upper for kw in _WRITE_KEYWORDS)


def _make_cache_key(cypher: str, params: dict) -> str:
    payload = cypher + "\x00" + json.dumps(params, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


class _CacheEntry:
    __slots__ = ("value", "expires_at")

    def __init__(self, value: list[dict], ttl: int) -> None:
        self.value = value
        self.expires_at = time.monotonic() + ttl


class _QueryCache:
    def __init__(self, max_entries: int = MAX_ENTRIES) -> None:
        self._store: dict[str, _CacheEntry] = {}
        self._lock = threading.Lock()
        self._max = max_entries
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> list[dict] | None:
        entry = self._store.get(key)
        if entry is None:
            self.misses += 1
            return None
        if time.monotonic() > entry.expires_at:
            with self._lock:
                self._store.pop(key, None)
            self.misses += 1
            return None
        self.hits += 1
        return entry.value

    def set(self, key: str, value: list[dict], ttl: int) -> None:
        with self._lock:
            if len(self._store) >= self._max:
                # evict oldest (insertion-order in Python 3.7+)
                oldest = next(iter(self._store))
                del self._store[oldest]
            self._store[key] = _CacheEntry(value, ttl)

    def invalidate(self) -> None:
        with self._lock:
            self._store.clear()
        logger.info("Neo4j query cache invalidated")

    @property
    def size(self) -> int:
        return len(self._store)

    def stats(self) -> dict[str, int]:
        return {"hits": self.hits, "misses": self.misses, "size": self.size}


_global_cache = _QueryCache()


def get_cache() -> _QueryCache:
    return _global_cache


class _CachedSession:
    """Thin wrapper around a real Neo4j session that intercepts read queries."""

    def __init__(self, real_session: Any, cache: _QueryCache, ttl: int) -> None:
        self._session = real_session
        self._cache = cache
        self._ttl = ttl

    def run(self, cypher: str, **params: Any) -> list[dict]:
        if _is_write_query(cypher):
            return list(self._session.run(cypher, **params))

        key = _make_cache_key(cypher, params)
        cached = self._cache.get(key)
        if cached is not None:
            logger.debug("Cache HIT key=%s...", key[:12])
            return cached

        rows = list(self._session.run(cypher, **params))
        result = [dict(row) for row in rows]
        self._cache.set(key, result, self._ttl)
        logger.debug("Cache MISS key=%s... stored %d rows", key[:12], len(result))
        return result

    def __getattr__(self, name: str) -> Any:
        return getattr(self._session, name)


@contextlib.contextmanager
def cached_session(
    driver: Driver,
    ttl: int = DEFAULT_TTL,
) -> Generator[Any, None, None]:
    """Context manager that yields a (possibly cached) session.

    When caching is disabled (default), this is a zero-cost passthrough.
    """
    with driver.session() as session:
        if not _CACHE_ENABLED:
            yield session
        else:
            yield _CachedSession(session, _global_cache, ttl)
