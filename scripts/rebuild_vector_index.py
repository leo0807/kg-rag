#!/usr/bin/env python3
"""
rebuild_vector_index.py — 离线全量重建 Milvus 向量索引

场景：
  - 更换 embedding 模型后需要重建所有向量
  - Milvus collection 损坏或迁移
  - 新增大量文档后批量写入向量

用法::

    cd backend
    python scripts/rebuild_vector_index.py \\
        --collection sections \\
        --batch-size 64 \\
        --doc-id CPS1220        # 可选，仅重建单文档
        --dry-run               # 只打印，不写入

    # 全量重建（所有文档）
    python scripts/rebuild_vector_index.py --collection sections

环境变量（从 .env 或 docker-compose 读取）::

    NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
    MILVUS_HOST, MILVUS_PORT
    EMBEDDING_MODEL / EMBEDDING_API_URL (按项目配置)
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path

# Ensure backend src is importable when running from scripts/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("DEBUG", "true")


def _fetch_sections(driver, doc_id: str) -> list[dict]:
    cypher = """
    MATCH (s:Section)
    WHERE $doc_id = '' OR s.doc_id = $doc_id
    RETURN s.chunk_id AS chunk_id, s.doc_id AS doc_id,
           s.content AS content, s.title AS title,
           s.number AS number
    ORDER BY s.doc_id, s.seq_index
    """
    with driver.session() as session:
        return [dict(r) for r in session.run(cypher, doc_id=doc_id)]


def _batch(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild Milvus vector index from Neo4j sections")
    parser.add_argument("--collection", default="sections", help="Milvus collection name")
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--doc-id",     default="", help="Limit to single doc (empty = all)")
    parser.add_argument("--dry-run",    action="store_true", help="Print stats, do not write")
    args = parser.parse_args()

    try:
        from neo4j import GraphDatabase
    except ImportError:
        log.error("neo4j driver missing: pip install neo4j")
        sys.exit(1)

    try:
        from src.services.retrieval.embedder import embed_texts
    except Exception as exc:
        log.error("Could not import embedder: %s", exc)
        sys.exit(1)

    try:
        from src.services.storage.milvus_store import upsert_sections
    except Exception as exc:
        log.error("Could not import milvus_store: %s", exc)
        sys.exit(1)

    from src.core.config import settings
    driver = GraphDatabase.driver(
        settings.NEO4J_URI,
        auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
    )

    log.info("Fetching sections from Neo4j (doc_id=%r)…", args.doc_id or "ALL")
    sections = _fetch_sections(driver, args.doc_id)
    driver.close()
    log.info("Found %d sections", len(sections))

    if not sections:
        log.warning("No sections found — nothing to do.")
        return

    if args.dry_run:
        log.info("[DRY RUN] Would embed+upsert %d sections in batches of %d", len(sections), args.batch_size)
        return

    total_written = 0
    for i, batch in enumerate(_batch(sections, args.batch_size), 1):
        texts = [f"{s.get('title', '')} {s.get('content', '')}".strip() for s in batch]
        try:
            vectors = embed_texts(texts)
        except Exception as exc:
            log.error("Embedding batch %d failed: %s — skipping", i, exc)
            continue

        enriched = []
        for sec, vec in zip(batch, vectors):
            enriched.append({**sec, "vector": vec})

        try:
            upsert_sections(args.collection, enriched)
            total_written += len(batch)
        except Exception as exc:
            log.error("Milvus upsert batch %d failed: %s — skipping", i, exc)
            continue

        log.info("Batch %d: wrote %d/%d sections", i, total_written, len(sections))
        time.sleep(0.05)  # back-pressure

    log.info("Done. Wrote %d / %d sections to collection %r", total_written, len(sections), args.collection)


if __name__ == "__main__":
    main()
