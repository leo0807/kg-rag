import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

log = logging.getLogger(__name__)


class GracefulShutdownTracker:
    """跟踪活跃 SSE 流，支持优雅关闭。"""

    def __init__(self):
        self._active_count = 0
        self._shutting_down = False
        self._zero_event = asyncio.Event()
        self._zero_event.set()

    @property
    def is_shutting_down(self) -> bool:
        return self._shutting_down

    @property
    def active_count(self) -> int:
        return self._active_count

    @asynccontextmanager
    async def track_stream(self) -> AsyncIterator[None]:
        if self._shutting_down:
            raise RuntimeError("Service is shutting down")

        self._active_count += 1
        self._zero_event.clear()
        log.debug("Stream started, active=%s", self._active_count)
        try:
            yield
        finally:
            self._active_count -= 1
            log.debug("Stream ended, active=%s", self._active_count)
            if self._active_count == 0:
                self._zero_event.set()

    async def drain(self, grace_period: float = 30.0) -> bool:
        self._shutting_down = True
        if self._active_count == 0:
            log.info("No active streams, shutdown immediately")
            return True

        log.warning(
            "Graceful shutdown: waiting for %s active streams (max %ss)",
            self._active_count,
            grace_period,
        )
        try:
            await asyncio.wait_for(self._zero_event.wait(), timeout=grace_period)
            log.info("All streams completed gracefully")
            return True
        except asyncio.TimeoutError:
            log.error(
                "Grace period %ss exceeded, %s streams still active. Forcing exit.",
                grace_period,
                self._active_count,
            )
            return False


shutdown_tracker = GracefulShutdownTracker()
