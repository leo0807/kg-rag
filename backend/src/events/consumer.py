"""
Kafka event consumer.
Consumes OPC-UA alerts and triggers WebSocket pushes to frontend.

Usage (standalone process):
    python -m backend.src.events.consumer
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys

log = logging.getLogger(__name__)

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
TOPICS = ["iot.constraint.alert", "doc.published", "graph.changed"]


async def handle_constraint_alert(payload: dict) -> None:
    """Push OPC-UA violation alert via Redis pub/sub → WebSocket."""
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
        await r.publish("ws:alerts", json.dumps({
            "type": "constraint_alert",
            "data": payload,
        }))
        await r.aclose()
        log.info("Pushed constraint alert: %s", payload.get("message", ""))
    except Exception as exc:
        log.warning("Failed to push WebSocket alert: %s", exc)


async def handle_doc_published(payload: dict) -> None:
    """Trigger knowledge subscription notifications for updated documents."""
    doc_id = payload.get("doc_id", "")
    if not doc_id:
        return
    try:
        import httpx
        backend_url = os.getenv("BACKEND_URL", "http://localhost:8000")
        api_key = os.getenv("BACKEND_API_KEY", "")
        async with httpx.AsyncClient() as c:
            await c.post(
                f"{backend_url}/api/subscriptions/notify",
                json={
                    "type": "document",
                    "target_id": doc_id,
                    "change_summary": f"文档 {payload.get('title', doc_id)} 已更新至版本 {payload.get('version', 'N/A')}",
                    "doc_id": doc_id,
                },
                headers={"X-API-Key": api_key},
                timeout=10,
            )
    except Exception as exc:
        log.warning("Subscription notification failed for %s: %s", doc_id, exc)


HANDLERS = {
    "iot.constraint.alert": handle_constraint_alert,
    "doc.published": handle_doc_published,
}


async def consume_loop() -> None:
    """Main async consumer loop."""
    try:
        from kafka import KafkaConsumer
    except ImportError:
        log.error("kafka-python not installed. Run: pip install kafka-python")
        return

    consumer = KafkaConsumer(
        *TOPICS,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id="kg-rag-consumer",
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        auto_offset_reset="latest",
        enable_auto_commit=True,
    )
    log.info("Kafka consumer started, listening on %s", TOPICS)

    for message in consumer:
        topic = message.topic
        payload = message.value
        handler = HANDLERS.get(topic)
        if handler:
            try:
                await handler(payload)
            except Exception as exc:
                log.error("Handler for %s failed: %s", topic, exc)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(consume_loop())


if __name__ == "__main__":
    main()
