"""Build a single global SPO knowledge graph from all documents.

Usage:
  python scripts/build_spo_global.py [--workers N] [--min-len N] [--max-sections N]

Runs as a background job; writes progress to stdout and Neo4j incrementally.
With --max-sections 500 you can get a meaningful graph in ~30 min (3 workers).
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from neo4j import GraphDatabase

from src.core.config import Settings
from src.services.graph.spo_extractor import _extract_spo_batch
from src.services.graph.spo_writer import (
    ensure_global_graph,
    merge_triples_into_graph,
    update_global_graph_counts,
)

settings = Settings()
GRAPH_ID = "spo_global"
BATCH_SIZE = 1   # 1 section per call — batch-of-3 hits 120s timeout; single is ~8s with /no_think


def fetch_sections(driver, min_len: int, max_sections: int) -> list[dict]:
    """Fetch sections ordered by richest documents first."""
    with driver.session() as s:
        result = s.run(
            """
            MATCH (d:Document)-[:HAS_SECTION]->(sec:Section)
            WHERE sec.content IS NOT NULL AND size(trim(sec.content)) >= $min_len
            WITH sec, d, size(trim(sec.content)) AS clen
            RETURN sec.chunk_id AS chunk_id,
                   sec.number   AS number,
                   sec.title    AS title,
                   sec.content  AS content,
                   d.name       AS doc_id,
                   clen
            ORDER BY clen DESC
            LIMIT $limit
            """,
            min_len=min_len, limit=max_sections,
        )
        return [dict(r) for r in result]


def process_batch(batch: list[dict]) -> tuple[list[str], list[dict]]:
    """Extract triples for a batch; returns (chunk_ids, spo_results)."""
    results = _extract_spo_batch(batch)
    return [s["chunk_id"] for s in batch], results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers",      type=int, default=5)
    parser.add_argument("--min-len",      type=int, default=150,
                        help="Minimum section content length (chars)")
    parser.add_argument("--max-sections", type=int, default=1500,
                        help="Max sections to process (richest first). Use -1 for all.")
    parser.add_argument("--graph-id",     default=GRAPH_ID)
    args = parser.parse_args()

    if args.max_sections == -1:
        args.max_sections = 999999

    driver = GraphDatabase.driver(
        settings.NEO4J_URI, auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
    )

    print(f"[SPO] 初始化全局图谱 {args.graph_id!r}")
    ensure_global_graph(driver, args.graph_id)

    print(f"[SPO] 加载章节 (≥{args.min_len}字, 最多 {args.max_sections} 节, 按内容长度降序)…")
    sections = fetch_sections(driver, args.min_len, args.max_sections)
    total_sec = len(sections)

    # Group into batches
    batches = [sections[i: i + BATCH_SIZE] for i in range(0, total_sec, BATCH_SIZE)]
    total_batches = len(batches)
    print(f"[SPO] {total_sec} 个章节 → {total_batches} 批 × {BATCH_SIZE}节/批，{args.workers} 线程并发")

    done_batches = 0
    done_secs = 0
    total_triples = 0
    start = time.time()

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(process_batch, b): b for b in batches}
        for fut in as_completed(futures):
            done_batches += 1
            try:
                chunk_ids, spo_results = fut.result()
                if spo_results:
                    merge_triples_into_graph(driver, args.graph_id, spo_results)
                    batch_triples = sum(len(r["triples"]) for r in spo_results)
                    total_triples += batch_triples
                done_secs += len(futures[fut])
            except Exception as exc:
                print(f"  ⚠ batch error: {exc}")

            if done_batches % 10 == 0 or done_batches == total_batches:
                elapsed = time.time() - start
                eta = (elapsed / done_batches) * (total_batches - done_batches) if done_batches else 0
                print(
                    f"  [{done_secs}/{total_sec}节 | {done_batches}/{total_batches}批] "
                    f"{total_triples} 条三元组 | "
                    f"已用 {elapsed:.0f}s | 预计剩余 {eta:.0f}s"
                )

    print("[SPO] 写入完成，更新统计…", flush=True)
    update_global_graph_counts(driver, args.graph_id)
    driver.close()
    elapsed = time.time() - start
    print(f"[SPO] 完成: {total_sec} 章节, {total_triples} 三元组 | 耗时 {elapsed:.0f}s")


if __name__ == "__main__":
    main()
