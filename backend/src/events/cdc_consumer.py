"""
CDC consumer: reads Debezium change events from Kafka and writes to ClickHouse.

Topics consumed:
  cdc.public.conversations
  cdc.public.query_feedback
  cdc.public.llm_usage

Run (standalone process):
  python -m backend.src.events.cdc_consumer

Requires:
  pip install kafka-python clickhouse-connect
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any

log = logging.getLogger(__name__)

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "localhost")
CLICKHOUSE_PORT = int(os.getenv("CLICKHOUSE_PORT", "8123"))

CDC_TOPICS = [
    "cdc.public.conversations",
    "cdc.public.query_feedback",
    "cdc.public.llm_usage",
]


def _get_ch_client():
    try:
        import clickhouse_connect
        return clickhouse_connect.get_client(
            host=CLICKHOUSE_HOST,
            port=CLICKHOUSE_PORT,
            database="aviation",
        )
    except ImportError:
        log.error("clickhouse-connect not installed: pip install clickhouse-connect")
        raise


def _extract(payload: dict[str, Any]) -> tuple[str, dict]:
    """Extract operation code and row data from a Debezium envelope."""
    op = payload.get("op", "c")  # c=create, u=update, d=delete, r=snapshot
    row = payload.get("after") or payload.get("before") or {}
    return op, row


def _dt(value: Any) -> datetime:
    """Coerce a Debezium timestamp field to a Python datetime."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        # Debezium emits epoch-milliseconds for timestamptz columns
        return datetime.utcfromtimestamp(value / 1000)
    if isinstance(value, str):
        for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
    return datetime.utcnow()


def handle_conversations(client, op: str, row: dict) -> None:
    client.insert(
        "conversations_changes",
        [[
            datetime.utcnow(),
            op,
            str(row.get("id", "")),
            str(row.get("user_id", "")),
            str(row.get("tenant_id", "")),
            str(row.get("doc_id", "")),
            int(row.get("query_count") or 0),
            _dt(row.get("created_at")),
            _dt(row.get("updated_at")),
        ]],
        column_names=[
            "event_time", "op", "session_id", "user_id",
            "tenant_id", "doc_id", "query_count", "created_at", "updated_at",
        ],
    )


def handle_query_feedback(client, op: str, row: dict) -> None:
    client.insert(
        "query_feedback_changes",
        [[
            datetime.utcnow(),
            op,
            str(row.get("id", "")),
            str(row.get("session_id", "")),
            str(row.get("user_id", "")),
            int(row.get("score") or 0),
            str(row.get("comment") or ""),
            _dt(row.get("created_at")),
        ]],
        column_names=[
            "event_time", "op", "feedback_id", "session_id",
            "user_id", "score", "comment", "created_at",
        ],
    )


def handle_llm_usage(client, op: str, row: dict) -> None:
    client.insert(
        "llm_usage_changes",
        [[
            datetime.utcnow(),
            op,
            str(row.get("id", "")),
            str(row.get("user_id", "")),
            str(row.get("tenant_id", "")),
            str(row.get("model") or ""),
            int(row.get("prompt_tokens") or 0),
            int(row.get("completion_tokens") or 0),
            float(row.get("cost_usd") or 0.0),
            _dt(row.get("created_at")),
        ]],
        column_names=[
            "event_time", "op", "usage_id", "user_id", "tenant_id",
            "model", "prompt_tokens", "completion_tokens", "cost_usd", "created_at",
        ],
    )


_HANDLERS = {
    "cdc.public.conversations":  handle_conversations,
    "cdc.public.query_feedback": handle_query_feedback,
    "cdc.public.llm_usage":      handle_llm_usage,
}


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    try:
        from kafka import KafkaConsumer
    except ImportError:
        log.error("kafka-python not installed: pip install kafka-python")
        return

    ch = _get_ch_client()
    consumer = KafkaConsumer(
        *CDC_TOPICS,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id="cdc-clickhouse-sync",
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        auto_offset_reset="earliest",
        enable_auto_commit=True,
    )
    log.info("CDC consumer started → ClickHouse %s:%s", CLICKHOUSE_HOST, CLICKHOUSE_PORT)

    for message in consumer:
        handler = _HANDLERS.get(message.topic)
        if not handler:
            continue
        try:
            op, row = _extract(message.value)
            if op == "d":
                continue  # deletes have no after-state; analytics only needs inserts/updates
            handler(ch, op, row)
            log.debug("%s op=%s row_id=%s", message.topic, op, row.get("id", "?"))
        except Exception as exc:
            log.error("Failed processing %s offset %s: %s", message.topic, message.offset, exc)


if __name__ == "__main__":
    main()
