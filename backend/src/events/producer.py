"""
Kafka event producer.
Publishes domain events on document ingest, query completion, and graph changes.

Topics:
  doc.published      — new/updated document ingested
  query.completed    — user query answered
  graph.changed      — node/relation created/updated/deleted
  iot.constraint.alert — OPC-UA constraint violation
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any

log = logging.getLogger(__name__)

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
_producer = None


def _get_producer():
    global _producer
    if _producer is not None:
        return _producer
    try:
        from kafka import KafkaProducer
        _producer = KafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP,
            value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode(),
            key_serializer=lambda k: k.encode() if k else None,
            acks="all",
            retries=3,
        )
        log.info("Kafka producer connected to %s", KAFKA_BOOTSTRAP)
    except ImportError:
        log.debug("kafka-python not installed — Kafka publishing disabled")
    except Exception as exc:
        log.warning("Kafka producer init failed: %s", exc)
    return _producer


def _publish(topic: str, key: str | None, payload: dict[str, Any]) -> None:
    producer = _get_producer()
    if producer is None:
        return
    try:
        payload["_published_at"] = datetime.utcnow().isoformat()
        producer.send(topic, key=key, value=payload)
        producer.flush(timeout=5)
    except Exception as exc:
        log.warning("Kafka publish failed (topic=%s): %s", topic, exc)


# ─── Public event publishers ──────────────────────────────────────────────────

def publish_document_ingested(doc_id: str, title: str,
                               version: str = "", operator: str = "") -> None:
    _publish("doc.published", doc_id, {
        "event": "doc.published",
        "doc_id": doc_id,
        "title": title,
        "version": version,
        "operator": operator,
    })


def publish_query_completed(user_id: str, question: str, strategy: str,
                             source_count: int, latency_ms: int) -> None:
    _publish("query.completed", user_id, {
        "event": "query.completed",
        "user_id": user_id,
        "question_len": len(question),
        "strategy": strategy,
        "source_count": source_count,
        "latency_ms": latency_ms,
    })


def publish_graph_changed(entity_type: str, entity_id: str,
                           operation: str, operator: str) -> None:
    _publish("graph.changed", entity_id, {
        "event": "graph.changed",
        "entity_type": entity_type,
        "entity_id": entity_id,
        "operation": operation,
        "operator": operator,
    })


def publish_constraint_alert(node_id: str, parameter: str,
                              value: float, unit: str, message: str) -> None:
    _publish("iot.constraint.alert", node_id, {
        "event": "iot.constraint.alert",
        "node_id": node_id,
        "parameter": parameter,
        "value": value,
        "unit": unit,
        "message": message,
    })
