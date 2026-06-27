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
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
BACKEND_API_KEY = os.getenv("BACKEND_API_KEY", "")

TOPICS = [
    "iot.constraint.alert",
    "doc.published",
    "graph.changed",
    "query.completed",
]


async def handle_constraint_alert(payload: dict) -> None:
    """Push OPC-UA violation alert via Redis → WebSocket, then trigger spec query."""
    # 1. WebSocket push
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

    # 2. 触发规范查询：自动检索与告警参数相关的规范条款
    node_id = payload.get("node_id", "")
    parameter = payload.get("parameter", "")
    if not parameter:
        return
    try:
        import httpx
        question = f"{parameter} 超限时的处置规范是什么？（节点 {node_id}）"
        async with httpx.AsyncClient() as c:
            await c.post(
                f"{BACKEND_URL}/api/query/auto",
                json={"question": question, "source": "iot_alert", "node_id": node_id},
                headers={"X-API-Key": BACKEND_API_KEY},
                timeout=15,
            )
    except Exception as exc:
        log.debug("Auto spec query for alert skipped: %s", exc)


async def handle_doc_published(payload: dict) -> None:
    """Trigger knowledge subscription notifications for updated documents."""
    doc_id = payload.get("doc_id", "")
    if not doc_id:
        return
    try:
        import httpx
        async with httpx.AsyncClient() as c:
            await c.post(
                f"{BACKEND_URL}/api/subscriptions/notify",
                json={
                    "type": "document",
                    "target_id": doc_id,
                    "change_summary": f"文档 {payload.get('title', doc_id)} 已更新至版本 {payload.get('version', 'N/A')}",
                    "doc_id": doc_id,
                },
                headers={"X-API-Key": BACKEND_API_KEY},
                timeout=10,
            )
    except Exception as exc:
        log.warning("Subscription notification failed for %s: %s", doc_id, exc)


async def handle_graph_changed(payload: dict) -> None:
    """Notify downstream ERP/MES systems of knowledge graph changes."""
    entity_type = payload.get("entity_type", "")
    entity_id = payload.get("entity_id", "")
    if not entity_id:
        return
    try:
        import httpx
        async with httpx.AsyncClient() as c:
            await c.post(
                f"{BACKEND_URL}/api/graph/sync-notify",
                json={
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "operation": payload.get("operation", ""),
                    "operator": payload.get("operator", ""),
                },
                headers={"X-API-Key": BACKEND_API_KEY},
                timeout=10,
            )
        log.info("Graph change notified: %s %s", entity_type, entity_id)
    except Exception as exc:
        log.debug("Graph sync-notify skipped: %s", exc)


async def handle_query_completed(payload: dict) -> None:
    """Feed completed query events into the data flywheel collector."""
    user_id = payload.get("user_id", "")
    if not user_id:
        return
    try:
        import httpx
        async with httpx.AsyncClient() as c:
            await c.post(
                f"{BACKEND_URL}/api/flywheel/collect",
                json={
                    "user_id": user_id,
                    "strategy": payload.get("strategy", ""),
                    "source_count": payload.get("source_count", 0),
                    "latency_ms": payload.get("latency_ms", 0),
                    "question_len": payload.get("question_len", 0),
                },
                headers={"X-API-Key": BACKEND_API_KEY},
                timeout=5,
            )
    except Exception as exc:
        log.debug("Flywheel collect skipped: %s", exc)


HANDLERS = {
    "iot.constraint.alert": handle_constraint_alert,
    "doc.published":        handle_doc_published,
    "graph.changed":        handle_graph_changed,
    "query.completed":      handle_query_completed,
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
