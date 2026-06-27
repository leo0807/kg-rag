"""
Flink CEP job: detect 3 consecutive OPC-UA constraint violations within 10 minutes.

Pattern: violation → violation → violation (same node_id, within WINDOW_SEC)
Output:  Kafka topic `iot.escalated.alert` + Redis pub/sub for WebSocket push.

Run inside Flink container (PyFlink mode):
  flink run -py /opt/flink/jobs/cep_violation_job.py

Run standalone (fallback mode):
  python cep_violation_job.py

Environment variables:
  KAFKA_BOOTSTRAP_SERVERS  default: kafka:9092
  REDIS_URL                default: redis://redis:6379/0
  CEP_WINDOW_SEC           default: 600  (10-minute detection window)
  CEP_THRESHOLD            default: 3    (consecutive violations to escalate)
"""
from __future__ import annotations

import json
import logging
import os
import time
from collections import defaultdict
from datetime import datetime, timezone

log = logging.getLogger(__name__)

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
REDIS_URL       = os.getenv("REDIS_URL", "redis://redis:6379/0")
WINDOW_SEC      = int(os.getenv("CEP_WINDOW_SEC", "600"))
THRESHOLD       = int(os.getenv("CEP_THRESHOLD", "3"))


def _build_escalated_alert(last_event: dict, count: int) -> dict:
    return {
        "type": "escalated_alert",
        "node_id": last_event.get("node_id", ""),
        "parameter": last_event.get("parameter", ""),
        "count": count,
        "window_sec": WINDOW_SEC,
        "message": f"连续 {count} 次超限：{last_event.get('message', '')}",
        "ts": datetime.now(timezone.utc).isoformat(),
    }


def run_pyflink() -> None:
    """PyFlink CEP job using the flink-cep library."""
    from pyflink.datastream import StreamExecutionEnvironment
    from pyflink.datastream.connectors.kafka import (
        KafkaSource, KafkaOffsetsInitializer,
    )
    from pyflink.cep import CEP, Pattern
    from pyflink.cep.pattern_select_function import PatternSelectFunction
    from pyflink.common.serialization import SimpleStringSchema
    from pyflink.common.watermark_strategy import WatermarkStrategy
    from pyflink.common.time import Time

    env = StreamExecutionEnvironment.get_execution_environment()
    env.set_parallelism(2)
    env.enable_checkpointing(30_000)

    source = (
        KafkaSource.builder()
        .set_bootstrap_servers(KAFKA_BOOTSTRAP)
        .set_topics("iot.constraint.alert")
        .set_group_id("flink-cep-violations")
        .set_starting_offsets(KafkaOffsetsInitializer.latest())
        .set_value_only_deserializer(SimpleStringSchema())
        .build()
    )

    keyed_stream = (
        env
        .from_source(source, WatermarkStrategy.for_monotonous_timestamps(), "IoTAlerts")
        .map(lambda raw: json.loads(raw))
        .key_by(lambda e: e.get("node_id", ""))
    )

    # Strict contiguity: events must follow each other for the same key
    pattern = (
        Pattern.begin("first")
        .next("second")
        .next("third")
        .within(Time.seconds(WINDOW_SEC))
    )

    class EscalateAlert(PatternSelectFunction):
        def select(self, pattern_map):
            last = pattern_map["third"][0]
            return _build_escalated_alert(last, 3)

    CEP.pattern(keyed_stream, pattern).select(EscalateAlert()).print()
    env.execute("OPC-UA CEP Violation Detector")


def run_fallback() -> None:
    """
    Fallback: kafka-python + in-memory per-node sliding window.
    Tracks timestamps of recent violations; fires when THRESHOLD events fall
    within WINDOW_SEC. Resets the window per-node after each escalation to
    avoid duplicate alerts for the same burst.
    """
    try:
        from kafka import KafkaConsumer, KafkaProducer
        import redis
    except ImportError as exc:
        log.error("Missing dependency: %s — pip install kafka-python redis", exc)
        return

    consumer = KafkaConsumer(
        "iot.constraint.alert",
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id="cep-violation-fallback",
        value_deserializer=lambda v: json.loads(v.decode()),
        auto_offset_reset="latest",
    )
    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode(),
    )
    try:
        r = redis.from_url(REDIS_URL, decode_responses=True)
        r.ping()
    except Exception:
        r = None
        log.warning("Redis unavailable — WebSocket push disabled")

    # {node_id: [(timestamp, event), ...]}
    windows: dict[str, list[tuple[float, dict]]] = defaultdict(list)
    log.info("CEP fallback started (window=%ds, threshold=%d)", WINDOW_SEC, THRESHOLD)

    for message in consumer:
        event = message.value
        node_id = event.get("node_id", "")
        if not node_id:
            continue

        now = time.monotonic()
        buf = windows[node_id]
        buf.append((now, event))

        # Evict events outside the sliding window
        cutoff = now - WINDOW_SEC
        windows[node_id] = [(t, e) for t, e in buf if t >= cutoff]

        if len(windows[node_id]) >= THRESHOLD:
            alert = _build_escalated_alert(event, len(windows[node_id]))

            producer.send("iot.escalated.alert", value=alert)
            producer.flush(timeout=3)
            log.warning(
                "Escalated alert: node=%s count=%d window=%ds",
                node_id, len(windows[node_id]), WINDOW_SEC,
            )

            if r:
                try:
                    r.publish("ws:alerts", json.dumps(alert))
                except Exception as exc:
                    log.debug("Redis publish error: %s", exc)

            # Reset window so next burst starts fresh
            windows[node_id] = []


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    try:
        import pyflink  # noqa: F401
        log.info("PyFlink detected — running CEP job")
        run_pyflink()
    except ImportError:
        log.warning("PyFlink not available — using kafka-python CEP fallback")
        run_fallback()


if __name__ == "__main__":
    main()
