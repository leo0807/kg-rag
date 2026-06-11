"""
J6.2: WebSocket endpoint for real-time dashboard events.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Dict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..services.realtime.event_stream import event_stream

router = APIRouter(prefix="/api/realtime", tags=["realtime"])

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Tracks active WebSocket connections."""

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self._connections.discard if hasattr(self._connections, "discard") else None
        try:
            self._connections.remove(ws)
        except ValueError:
            pass

    async def broadcast(self, msg: Dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        for ws in list(self._connections):
            try:
                await ws.send_json(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    @property
    def count(self) -> int:
        return len(self._connections)


manager = ConnectionManager()


@router.websocket("/dashboard")
async def dashboard_ws(ws: WebSocket) -> None:
    await manager.connect(ws)
    logger.info("WebSocket connected, total=%d", manager.count)

    # Send initial connection ack
    await ws.send_json({"event": "connected", "ts": time.time(), "data": {"total_connections": manager.count}})

    # Background task: subscribe to Redis and forward to this connection
    async def _forward() -> None:
        async for event in event_stream.subscribe(channel="dashboard", timeout=3600):
            try:
                await ws.send_json(event)
            except Exception:
                break

    fwd_task = asyncio.create_task(_forward())

    # Heartbeat: ping every 30s so proxies don't close the connection
    try:
        while True:
            try:
                msg = await asyncio.wait_for(ws.receive_text(), timeout=30.0)
                if msg == "ping":
                    await ws.send_json({"event": "pong", "ts": time.time(), "data": {}})
            except asyncio.TimeoutError:
                await ws.send_json({"event": "heartbeat", "ts": time.time(), "data": {}})
            except WebSocketDisconnect:
                break
    finally:
        fwd_task.cancel()
        manager.disconnect(ws)
        logger.info("WebSocket disconnected, total=%d", manager.count)


@router.get("/dashboard/stats")
async def ws_stats() -> Dict[str, Any]:
    return {"connected_clients": manager.count}
