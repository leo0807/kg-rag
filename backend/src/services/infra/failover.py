"""
I7.2: Service failover detection and automatic switchover.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class ServiceNode:
    name: str
    url: str
    health_path: str = "/health"
    is_primary: bool = True
    is_healthy: bool = True
    last_checked: float = field(default_factory=time.time)
    fail_count: int = 0


@dataclass
class FailoverEvent:
    timestamp: float
    service: str
    from_node: str
    to_node: str
    reason: str


class ServiceFailover:
    """
    Monitors service nodes and switches traffic to healthy replicas.
    Calls registered callbacks on failover so the app can update its connections.
    """

    MAX_FAILURES = 3         # consecutive failures before marking unhealthy
    CHECK_INTERVAL = 30.0    # seconds between health probes
    RECOVERY_TIMEOUT = 60.0  # seconds before re-checking a failed node

    def __init__(self) -> None:
        self._services: Dict[str, List[ServiceNode]] = {}
        self._callbacks: Dict[str, List[Callable]] = {}
        self._events: List[FailoverEvent] = []
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def register(
        self,
        service_name: str,
        nodes: List[ServiceNode],
        on_failover: Optional[Callable] = None,
    ) -> None:
        self._services[service_name] = nodes
        if on_failover:
            self._callbacks.setdefault(service_name, []).append(on_failover)

    def get_active_node(self, service_name: str) -> Optional[ServiceNode]:
        nodes = self._services.get(service_name, [])
        # Prefer primary; fall back to first healthy replica
        for n in nodes:
            if n.is_primary and n.is_healthy:
                return n
        for n in nodes:
            if n.is_healthy:
                return n
        return None

    async def check_node(self, node: ServiceNode) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as c:
                r = await c.get(f"{node.url.rstrip('/')}{node.health_path}")
                healthy = r.status_code < 500
        except Exception:
            healthy = False

        node.last_checked = time.time()
        if healthy:
            if not node.is_healthy:
                logger.info("节点恢复: %s (%s)", node.name, node.url)
            node.is_healthy = True
            node.fail_count = 0
        else:
            node.fail_count += 1
            if node.fail_count >= self.MAX_FAILURES and node.is_healthy:
                node.is_healthy = False
                logger.warning("节点故障: %s (%s), 失败 %d 次", node.name, node.url, node.fail_count)
                await self._trigger_failover(node)
        return healthy

    async def _trigger_failover(self, failed_node: ServiceNode) -> None:
        service_name = next(
            (k for k, nodes in self._services.items() if failed_node in nodes), None
        )
        if not service_name:
            return
        fallback = self.get_active_node(service_name)
        event = FailoverEvent(
            timestamp=time.time(),
            service=service_name,
            from_node=failed_node.name,
            to_node=fallback.name if fallback else "none",
            reason=f"连续失败 {failed_node.fail_count} 次",
        )
        self._events.append(event)
        logger.error(
            "故障转移: %s → %s → %s",
            service_name, failed_node.name, event.to_node,
        )
        for cb in self._callbacks.get(service_name, []):
            try:
                await cb(event) if asyncio.iscoroutinefunction(cb) else cb(event)
            except Exception as e:
                logger.warning("故障转移回调异常: %s", e)

        # Notify ops (non-blocking)
        asyncio.create_task(self._notify_ops(event))

    async def _notify_ops(self, event: FailoverEvent) -> None:
        try:
            from ...core.config import settings
            webhook = getattr(settings, "DINGTALK_WEBHOOK", "") or \
                      getattr(settings, "WECOM_WEBHOOK", "")
            if not webhook:
                return
            msg = (
                f"⚠ 服务故障转移\n"
                f"服务: {event.service}\n"
                f"{event.from_node} → {event.to_node}\n"
                f"原因: {event.reason}"
            )
            async with httpx.AsyncClient(timeout=5.0) as c:
                await c.post(webhook, json={"msgtype": "text", "text": {"content": msg}})
        except Exception:
            pass

    async def _monitor_loop(self) -> None:
        while self._running:
            for nodes in self._services.values():
                for node in nodes:
                    if not node.is_healthy and \
                       time.time() - node.last_checked < self.RECOVERY_TIMEOUT:
                        continue
                    await self.check_node(node)
            await asyncio.sleep(self.CHECK_INTERVAL)

    def start(self) -> None:
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._monitor_loop())
            logger.info("故障转移监控已启动")

    def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()

    def status(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for svc, nodes in self._services.items():
            result[svc] = {
                "nodes": [
                    {"name": n.name, "url": n.url,
                     "primary": n.is_primary, "healthy": n.is_healthy,
                     "fail_count": n.fail_count}
                    for n in nodes
                ],
                "active": self.get_active_node(svc).name
                if self.get_active_node(svc) else None,
            }
        return result

    def recent_events(self, limit: int = 20) -> List[Dict[str, Any]]:
        return [
            {"ts": e.timestamp, "service": e.service,
             "from": e.from_node, "to": e.to_node, "reason": e.reason}
            for e in self._events[-limit:]
        ]


failover_manager = ServiceFailover()
