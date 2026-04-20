"""
services/health.py
服务健康监控 — 启动时及运行时定期 ping Neo4j / Milvus / Elasticsearch。
连接失败时置降级标志，供检索层跳过不可用后端而非直接 500。
"""
import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)

PING_INTERVAL_SECONDS = 30   # 健康检查间隔


class ServiceState(str, Enum):
    OK      = "ok"
    DOWN    = "down"
    UNKNOWN = "unknown"


@dataclass
class ServiceStatus:
    name:       str
    state:      ServiceState = ServiceState.UNKNOWN
    last_check: float        = 0.0
    error:      str          = ""
    latency_ms: float        = 0.0  # 新增：最近一次 I/O 耗时

    @property
    def is_ok(self) -> bool:
        return self.state == ServiceState.OK

    def to_dict(self) -> dict:
        return {
            "state":      self.state,
            "error":      self.error,
            "latency_ms": round(self.latency_ms, 2),
            "last_check": int(self.last_check) if self.last_check else None,
        }


class ServiceHealthMonitor:
    """
    全局单例，维护各依赖服务的连接状态。

    使用方式：
        from .services.health import health_monitor
        if health_monitor.milvus.is_ok:
            # 执行向量检索
    """

    def __init__(self):
        self.neo4j         = ServiceStatus("neo4j")
        self.milvus        = ServiceStatus("milvus")
        self.elasticsearch = ServiceStatus("elasticsearch")
        self._task: Optional[asyncio.Task] = None  # type: ignore[type-arg]

    # ── 各服务 ping ─────────────────────────────────────────────────────────

    def ping_neo4j(self) -> bool:
        start = time.time()
        try:
            from ..core.database import get_driver
            with get_driver().session() as s:
                s.run("RETURN 1").single()
            self.neo4j.state = ServiceState.OK
            self.neo4j.error = ""
        except Exception as exc:
            self.neo4j.state = ServiceState.DOWN
            self.neo4j.error = str(exc)
        self.neo4j.latency_ms = (time.time() - start) * 1000
        self.neo4j.last_check = time.time()
        return self.neo4j.is_ok

    def ping_milvus(self) -> bool:
        start = time.time()
        try:
            from pymilvus import utility
            utility.list_collections()
            self.milvus.state = ServiceState.OK
            self.milvus.error = ""
        except Exception as exc:
            self.milvus.state = ServiceState.DOWN
            self.milvus.error = str(exc)
        self.milvus.latency_ms = (time.time() - start) * 1000
        self.milvus.last_check = time.time()
        return self.milvus.is_ok

    def ping_es(self) -> bool:
        start = time.time()
        try:
            from .es_store import get_es
            if not get_es().ping():
                raise ConnectionError("ES ping 返回 False")
            self.elasticsearch.state = ServiceState.OK
            self.elasticsearch.error = ""
        except Exception as exc:
            self.elasticsearch.state = ServiceState.DOWN
            self.elasticsearch.error = str(exc)
        self.elasticsearch.latency_ms = (time.time() - start) * 1000
        self.elasticsearch.last_check = time.time()
        return self.elasticsearch.is_ok

    def check_all(self) -> dict:
        """同步检查所有服务（启动时使用）"""
        results = {
            "neo4j":         self.ping_neo4j(),
            "milvus":        self.ping_milvus(),
            "elasticsearch": self.ping_es(),
        }
        for name, ok in results.items():
            status = getattr(self, name if name != "elasticsearch" else "elasticsearch")
            if ok:
                logger.info("健康检查 [OK]  %s", name)
            else:
                logger.warning(
                    "健康检查 [DOWN] %s — %s | 将降级运行（跳过该后端）",
                    name, status.error,
                )
        return results

    def to_dict(self) -> dict:
        return {
            "neo4j":         self.neo4j.to_dict(),
            "milvus":        self.milvus.to_dict(),
            "elasticsearch": self.elasticsearch.to_dict(),
        }

    # ── 后台定期检查 ─────────────────────────────────────────────────────────

    async def _loop(self):
        while True:
            await asyncio.sleep(PING_INTERVAL_SECONDS)
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self.check_all)
            except Exception as exc:
                logger.debug("健康检查循环异常（忽略）: %s", exc)

    def start_background_task(self):
        """在 asyncio event loop 已启动后调用（lifespan 内）"""
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop())
            logger.info(
                "健康检查后台任务已启动，每 %ds 检查一次",
                PING_INTERVAL_SECONDS,
            )

    def stop_background_task(self):
        if self._task and not self._task.done():
            self._task.cancel()


# ── 全局单例 ─────────────────────────────────────────────────────────────────
health_monitor = ServiceHealthMonitor()
