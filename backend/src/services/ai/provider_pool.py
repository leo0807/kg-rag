from __future__ import annotations

"""LLM Provider Pool — 按优先级自动故障转移。"""

import asyncio
import logging
import threading
from dataclasses import dataclass
from datetime import datetime
from typing import AsyncGenerator

from .errors import LLMError
from .providers import OpenAICompatProvider

logger = logging.getLogger(__name__)


@dataclass
class ProviderConfig:
    name: str
    url: str
    key: str
    model: str
    priority: int = 1


class LLMProviderPool:
    """多 LLM Provider 池，支持自动故障转移与健康恢复。"""

    def __init__(self, providers: list[ProviderConfig], max_consecutive_failures: int = 3):
        if not providers:
            raise ValueError("Provider pool requires at least one provider")
        self._providers = sorted(providers, key=lambda p: p.priority)
        self._max = max_consecutive_failures
        self._stats: dict[str, dict] = {
            p.name: {
                "healthy": True,
                "consecutive_failures": 0,
                "total_calls": 0,
                "success_calls": 0,
                "last_success": None,
                "last_failure": None,
                "last_reason": "",
            }
            for p in self._providers
        }
        self._locks = {p.name: threading.Lock() for p in self._providers}
        self._health_task: asyncio.Task | None = None  # type: ignore[type-arg]

    @property
    def model_name(self) -> str:
        for p in self._providers:
            if self._stats[p.name]["healthy"]:
                return p.model
        return self._providers[0].model

    def _make(self, cfg: ProviderConfig) -> OpenAICompatProvider:
        return OpenAICompatProvider(cfg.url, cfg.key, cfg.model)

    def _active(self) -> list[ProviderConfig]:
        active = [p for p in self._providers if self._stats[p.name]["healthy"]]
        return active or list(self._providers)  # last-resort: try all

    def _ok(self, name: str) -> None:
        with self._locks[name]:
            s = self._stats[name]
            s["healthy"] = True
            s["consecutive_failures"] = 0
            s["total_calls"] += 1
            s["success_calls"] += 1
            s["last_success"] = datetime.utcnow()

    def _fail(self, name: str, reason: str) -> None:
        with self._locks[name]:
            s = self._stats[name]
            s["consecutive_failures"] += 1
            s["total_calls"] += 1
            s["last_failure"] = datetime.utcnow()
            s["last_reason"] = reason[:200]
            if s["consecutive_failures"] >= self._max and s["healthy"]:
                s["healthy"] = False
                logger.error(
                    "[LLM_POOL] %s 连续失败 %d 次，标记为不健康",
                    name, s["consecutive_failures"],
                )

    def chat_with_fallback(self, messages: list[dict], **kwargs) -> str:
        errors: list[str] = []
        for p in self._active():
            try:
                logger.info("[LLM_POOL] 尝试 %s model=%s", p.name, p.model)
                result = self._make(p).chat(messages, **kwargs)
                self._ok(p.name)
                return result
            except Exception as exc:
                msg = str(exc)[:200]
                errors.append(f"{p.name}: {msg}")
                self._fail(p.name, msg)
                logger.warning("[LLM_POOL] %s 失败: %s，尝试下一个", p.name, msg)
        raise LLMError(
            "all_providers_failed",
            f"所有LLM provider均失败: {'; '.join(errors)}",
            endpoint="provider_pool",
        )

    async def stream_chat_with_fallback(
        self, messages: list[dict], **kwargs
    ) -> AsyncGenerator[str, None]:
        self._maybe_start_health_check()
        errors: list[str] = []
        for p in self._active():
            logger.info("[LLM_POOL] 流式尝试 %s model=%s", p.name, p.model)
            first_seen = False
            try:
                async for chunk in self._make(p).stream_chat(messages, **kwargs):
                    first_seen = True
                    yield chunk
                self._ok(p.name)
                return
            except Exception as exc:
                if first_seen:
                    self._fail(p.name, str(exc)[:200])
                    raise  # already streaming → can't fall over
                msg = str(exc)[:200]
                errors.append(f"{p.name}: {msg}")
                self._fail(p.name, msg)
                logger.warning("[LLM_POOL] %s 流式失败（首字前）: %s，尝试下一个", p.name, msg)
        raise LLMError(
            "all_providers_failed",
            f"所有LLM provider流式调用均失败: {'; '.join(errors)}",
            endpoint="provider_pool",
        )

    def _maybe_start_health_check(self) -> None:
        if self._health_task is not None:
            return
        try:
            loop = asyncio.get_running_loop()
            self._health_task = loop.create_task(self.health_check_loop())
        except RuntimeError:
            pass  # sync context — health check not needed

    async def health_check_loop(self) -> None:
        """每60s探测不健康的 provider，成功则恢复健康标记。"""
        while True:
            await asyncio.sleep(60)
            for p in self._providers:
                if not self._stats[p.name]["healthy"]:
                    if await self._probe(p):
                        with self._locks[p.name]:
                            self._stats[p.name]["healthy"] = True
                            self._stats[p.name]["consecutive_failures"] = 0
                        logger.info("[LLM_POOL] %s 探测成功，恢复为健康", p.name)

    async def _probe(self, p: ProviderConfig) -> bool:
        try:
            await asyncio.to_thread(
                self._make(p).chat,
                [{"role": "user", "content": "ping"}],
                max_tokens=1,
                timeout=10,
            )
            return True
        except Exception as e:
            logger.debug("[LLM_POOL] %s 探测失败: %s", p.name, e)
            return False

    def get_status(self) -> list[dict]:
        result = []
        for p in self._providers:
            s = self._stats[p.name]
            total = max(s["total_calls"], 1)
            result.append({
                "name": p.name,
                "model": p.model,
                "url": p.url,
                "healthy": s["healthy"],
                "consecutive_failures": s["consecutive_failures"],
                "total_calls": s["total_calls"],
                "success_rate": round(s["success_calls"] / total, 3),
                "last_success": s["last_success"].isoformat() if s["last_success"] else None,
                "last_failure": s["last_failure"].isoformat() if s["last_failure"] else None,
                "last_failure_reason": s["last_reason"],
            })
        return result


# ── 进程级单例 ────────────────────────────────────────────────────────────
_pool: LLMProviderPool | None = None
_pool_lock = threading.Lock()


def get_provider_pool() -> LLMProviderPool | None:
    return _pool


def build_pool_from_settings(s) -> LLMProviderPool | None:
    """从 settings 构建 provider pool；如未启用故障转移则返回 None。"""
    global _pool
    if not getattr(s, "LLM_FAILOVER_ENABLED", False):
        return None
    if _pool is not None:
        return _pool
    with _pool_lock:
        if _pool is not None:
            return _pool
        providers = [
            ProviderConfig(name="primary", url=s.LLM_API_URL, key=s.LLM_API_KEY,
                           model=s.LLM_MODEL, priority=1),
        ]
        if getattr(s, "LLM_FALLBACK_1_URL", ""):
            providers.append(ProviderConfig(
                name="fallback_1", url=s.LLM_FALLBACK_1_URL,
                key=getattr(s, "LLM_FALLBACK_1_KEY", ""),
                model=getattr(s, "LLM_FALLBACK_1_MODEL", ""),
                priority=2,
            ))
        if getattr(s, "LLM_FALLBACK_2_URL", ""):
            providers.append(ProviderConfig(
                name="fallback_2", url=s.LLM_FALLBACK_2_URL,
                key=getattr(s, "LLM_FALLBACK_2_KEY", ""),
                model=getattr(s, "LLM_FALLBACK_2_MODEL", ""),
                priority=3,
            ))
        _pool = LLMProviderPool(providers)
        logger.info("[LLM_POOL] 初始化完成，%d 个 provider: %s",
                    len(providers), [p.name for p in providers])
        return _pool
