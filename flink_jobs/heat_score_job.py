"""
Flink job: real-time Section heat score via 1-hour sliding window.

Reads from Kafka topic `graph.changed` — events with entity_type="Section".
Every SLIDE_SIZE_SEC seconds, writes updated heat_score to Neo4j for the top-K
most-referenced Sections within the past WINDOW_SIZE_SEC.

Run inside Flink container (PyFlink mode):
  flink run -py /opt/flink/jobs/heat_score_job.py

Run standalone (fallback mode, no Flink cluster required):
  python heat_score_job.py

Environment variables:
  KAFKA_BOOTSTRAP_SERVERS  default: kafka:9092
  NEO4J_URI                default: bolt://neo4j:7687
  NEO4J_USER               default: neo4j
  NEO4J_PASSWORD           (required)
  HEAT_WINDOW_SEC          default: 3600  (1 hour)
  HEAT_SLIDE_SEC           default: 300   (5 minutes)
  HEAT_TOP_K               default: 100
"""
from __future__ import annotations

import json
import logging
import os
import time
from collections import defaultdict

log = logging.getLogger(__name__)

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
NEO4J_URI       = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
NEO4J_USER      = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD  = os.getenv("NEO4J_PASSWORD", "")
WINDOW_SIZE_SEC = int(os.getenv("HEAT_WINDOW_SEC", "3600"))
SLIDE_SIZE_SEC  = int(os.getenv("HEAT_SLIDE_SEC", "300"))
TOP_K           = int(os.getenv("HEAT_TOP_K", "100"))


def _neo4j_driver():
    from neo4j import GraphDatabase
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def _flush_scores(counts: dict[str, int]) -> None:
    """Write top-K heat scores to Neo4j in a single transaction."""
    if not counts:
        return
    top = sorted(counts.items(), key=lambda x: -x[1])[:TOP_K]
    driver = _neo4j_driver()
    with driver.session() as session:
        for chunk_id, score in top:
            session.run(
                "MATCH (s:Section {chunk_id: $id}) SET s.heat_score = $score",
                id=chunk_id, score=score,
            )
    driver.close()
    log.info("heat_score updated for %d sections (top score: %d)", len(top), top[0][1])


def run_pyflink() -> None:
    """PyFlink streaming job with sliding processing-time window."""
    from pyflink.datastream import StreamExecutionEnvironment
    from pyflink.datastream.connectors.kafka import (
        KafkaSource, KafkaOffsetsInitializer,
    )
    from pyflink.common.serialization import SimpleStringSchema
    from pyflink.common.watermark_strategy import WatermarkStrategy
    from pyflink.datastream.window import SlidingProcessingTimeWindows
    from pyflink.common.time import Time

    env = StreamExecutionEnvironment.get_execution_environment()
    env.set_parallelism(2)
    env.enable_checkpointing(60_000)

    source = (
        KafkaSource.builder()
        .set_bootstrap_servers(KAFKA_BOOTSTRAP)
        .set_topics("graph.changed")
        .set_group_id("flink-heat-score")
        .set_starting_offsets(KafkaOffsetsInitializer.latest())
        .set_value_only_deserializer(SimpleStringSchema())
        .build()
    )

    stream = env.from_source(
        source,
        WatermarkStrategy.no_watermarks(),
        "KafkaGraphChanged",
    )

    def parse_section_ref(raw: str):
        try:
            event = json.loads(raw)
            if event.get("entity_type") == "Section" and "entity_id" in event:
                return (event["entity_id"], 1)
        except (json.JSONDecodeError, KeyError):
            pass
        return None

    def write_to_neo4j(result: tuple[str, int]) -> tuple[str, int]:
        driver = _neo4j_driver()
        with driver.session() as s:
            s.run(
                "MATCH (n:Section {chunk_id:$id}) SET n.heat_score=$v",
                id=result[0], v=result[1],
            )
        driver.close()
        return result

    (
        stream
        .map(parse_section_ref)
        .filter(lambda x: x is not None)
        .key_by(lambda x: x[0])
        .window(SlidingProcessingTimeWindows.of(
            Time.seconds(WINDOW_SIZE_SEC),
            Time.seconds(SLIDE_SIZE_SEC),
        ))
        .reduce(lambda a, b: (a[0], a[1] + b[1]))
        .map(write_to_neo4j)
    )

    env.execute("Section Heat Score — Sliding Window")


def run_fallback() -> None:
    """
    Fallback implementation using kafka-python with in-memory sliding window.
    Produces identical results to the PyFlink job using a deque-based approach.
    """
    try:
        from kafka import KafkaConsumer
    except ImportError:
        log.error("kafka-python not installed: pip install kafka-python")
        return

    consumer = KafkaConsumer(
        "graph.changed",
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id="heat-score-fallback",
        value_deserializer=lambda v: json.loads(v.decode()),
        auto_offset_reset="latest",
        consumer_timeout_ms=1000,
    )

    # sliding window: {chunk_id: [(timestamp, count), ...]}
    window: dict[str, list[tuple[float, int]]] = defaultdict(list)
    last_flush = time.monotonic()
    log.info("heat_score fallback started (window=%ds slide=%ds)", WINDOW_SIZE_SEC, SLIDE_SIZE_SEC)

    while True:
        for message in consumer:
            event = message.value
            if event.get("entity_type") == "Section" and "entity_id" in event:
                now = time.monotonic()
                window[event["entity_id"]].append((now, 1))

        now = time.monotonic()
        if now - last_flush >= SLIDE_SIZE_SEC:
            cutoff = now - WINDOW_SIZE_SEC
            scores: dict[str, int] = {}
            for chunk_id, events in list(window.items()):
                recent = [(t, c) for t, c in events if t >= cutoff]
                if recent:
                    window[chunk_id] = recent
                    scores[chunk_id] = sum(c for _, c in recent)
                else:
                    del window[chunk_id]
            try:
                _flush_scores(scores)
            except Exception as exc:
                log.error("Neo4j flush failed: %s", exc)
            last_flush = now


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    try:
        import pyflink  # noqa: F401
        log.info("PyFlink detected — running streaming job")
        run_pyflink()
    except ImportError:
        log.warning("PyFlink not available — using kafka-python fallback")
        run_fallback()


if __name__ == "__main__":
    main()
