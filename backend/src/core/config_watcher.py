from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Optional

from .config import ENV_FILE_PATH, reload_reloadable_settings

log = logging.getLogger(__name__)


class ConfigWatcher:
    def __init__(self, path: Path = ENV_FILE_PATH, interval_seconds: float = 2.0):
        self.path = path
        self.interval_seconds = interval_seconds
        self._task: Optional[asyncio.Task[None]] = None
        self._stop_event = asyncio.Event()
        self._last_signature = self._stat_signature()

    def _stat_signature(self) -> tuple[int, int] | None:
        try:
            stat = self.path.stat()
        except FileNotFoundError:
            return None
        return (stat.st_mtime_ns, stat.st_size)

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run(), name="config-watcher")
        log.info("Config watcher started for %s", self.path)

    async def stop(self) -> None:
        if not self._task:
            return
        self._stop_event.set()
        try:
            await self._task
        finally:
            self._task = None
            log.info("Config watcher stopped")

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            await asyncio.sleep(self.interval_seconds)
            signature = self._stat_signature()
            if signature == self._last_signature:
                continue
            self._last_signature = signature
            changed = reload_reloadable_settings()
            if changed:
                log.info("Config reloaded from %s: %s", self.path, ", ".join(sorted(changed)))
            else:
                log.info("Config file changed but no reloadable field changed: %s", self.path)


config_watcher = ConfigWatcher()

