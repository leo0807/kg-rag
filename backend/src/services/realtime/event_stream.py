"""
J6.1: Real-time event stream using Redis Pub/Sub.
"""
from __future__ import annotations

import json
import logging
import time
from typing import AsyncGenerator, Dict, Any, Optional

logger = logging.getLogger(__name__)

EVENT_TYPES = {
    "query.started",
    "query.completed",
    "feedback.submitted",
    "error.occurred",
    "user.login",
    "document.ingested",
}


class EventStream:
    """Publish events to Redis and subscribe to them for real-time streaming."""

    def __init__(self) -> None:
        self._redis_client = None

    def _get_redis(self):
        if self._redis_client is None:
            try:
                import redis.asyncio as aioredis
                from ...core.config import settings
                url = getattr(settings, "REDIS_URL", "redis://localhost:6379")
                self._redis_client = aioredis.from_url(url, decode_responses=True)
            except Exception as e:
                logger.debug("Redis not available for EventStream: %s", e)
        return self._redis_client

    async def publish(
        self,
        event_type: str,
        payload: Dict[str, Any],
        channel: str = "dashboard",
    ) -> None:
        r = self._get_redis()
        if r is None:
            return
        msg = json.dumps({
            "event": event_type,
            "ts": time.time(),
            "data": payload,
        })
        try:
            await r.publish(channel, msg)
        except Exception as e:
            logger.debug("EventStream.publish failed: %s", e)

    async def subscribe(
        self,
        channel: str = "dashboard",
        timeout: float = 30.0,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        r = self._get_redis()
        if r is None:
            return

        pubsub = r.pubsub()
        await pubsub.subscribe(channel)
        deadline = time.time() + timeout

        try:
            while time.time() < deadline:
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if msg and msg.get("type") == "message":
                    try:
                        yield json.loads(msg["data"])
                    except json.JSONDecodeError:
                        pass
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()

    async def emit_query(
        self, user_id: str, question: str, status: str = "completed", latency_ms: int = 0
    ) -> None:
        await self.publish(
            f"query.{status}",
            {"user_id": user_id, "question": question[:100], "latency_ms": latency_ms},
        )

    async def emit_error(self, error_type: str, message: str, path: str = "") -> None:
        await self.publish(
            "error.occurred",
            {"type": error_type, "message": message[:200], "path": path},
        )

    async def emit_feedback(self, user_id: str, rating: int) -> None:
        await self.publish(
            "feedback.submitted",
            {"user_id": user_id, "rating": rating},
        )


event_stream = EventStream()
