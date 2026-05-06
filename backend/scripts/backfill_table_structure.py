"""
回填 Table 节点的 headers / col_count / structured_data 字段。

已有 Table 节点只有 rows_json（JSON 字符串），需要把解析结果写回 Neo4j。
Milvus 行级向量回填需要重新解析 rows_json，嵌入并 upsert。

Usage:
    python -m scripts.backfill_table_structure           # 正式运行
    python -m scripts.backfill_table_structure --dry-run # 只打印，不写数据库
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _parse_rows(rows_json_str: str) -> list[list[str]]:
    try:
        return json.loads(rows_json_str) if rows_json_str else []
    except Exception:
        return []


def _build_structured_data(headers: list[str], data_rows: list[list[str]]) -> str:
    if not headers or not data_rows:
        return "[]"
    records = []
    for row in data_rows:
        records.append({headers[i]: (row[i] if i < len(row) else "") for i in range(len(headers))})
    return json.dumps(records, ensure_ascii=False)


def backfill_neo4j(driver, dry_run: bool) -> int:
    with driver.session() as session:
        result = session.run("""
            MATCH (t:Table)
            WHERE t.rows_json IS NOT NULL AND (t.headers IS NULL OR t.structured_data IS NULL)
            RETURN t.table_id AS table_id, t.rows_json AS rows_json
        """)
        rows = [(r["table_id"], r["rows_json"]) for r in result]

    logger.info("待回填 Table 节点: %d", len(rows))
    if not rows:
        return 0

    updated = 0
    with driver.session() as session:
        for table_id, rows_json_str in rows:
            raw = _parse_rows(rows_json_str or "")
            headers = raw[0] if raw else []
            data_rows = raw[1:] if len(raw) > 1 else []
            structured_data = _build_structured_data(headers, data_rows)
            logger.info("  %s  headers=%s  data_rows=%d", table_id, headers[:3], len(data_rows))
            if not dry_run:
                session.run("""
                    MATCH (t:Table {table_id: $table_id})
                    SET t.headers         = $headers,
                        t.col_count       = $col_count,
                        t.structured_data = $structured_data
                """, table_id=table_id, headers=headers,
                     col_count=len(headers), structured_data=structured_data)
            updated += 1

    return updated


def backfill_milvus(driver, dry_run: bool) -> int:
    """为所有 Table 节点生成行级向量并写入 Milvus。"""
    try:
        from src.services.retrieval.embedder import embed_texts
        from src.services.storage.milvus_store import upsert_sections
    except ImportError as e:
        logger.warning("Milvus/embedder 不可用，跳过向量回填: %s", e)
        return 0

    with driver.session() as session:
        result = session.run("""
            MATCH (t:Table)
            WHERE t.rows_json IS NOT NULL
            RETURN t.table_id AS table_id, t.doc_id AS doc_id, t.rows_json AS rows_json
        """)
        tables = [dict(r) for r in result]

    logger.info("待向量回填 Table 节点: %d", len(tables))

    row_records: list[dict] = []
    for table in tables:
        raw = _parse_rows(table.get("rows_json") or "")
        headers = raw[0] if raw else []
        for i, row in enumerate(raw[1:], start=1):
            text = " | ".join(f"{h}: {v}" for h, v in zip(headers, row) if h and (v or "").strip())
            if text.strip():
                row_records.append({
                    "chunk_id": f"{table['table_id']}_row_{i}",
                    "doc_id": table["doc_id"] or "",
                    "text": text,
                })

    logger.info("总行级文本数: %d", len(row_records))
    if not row_records or dry_run:
        return len(row_records)

    batch_size = 64
    total_written = 0
    for i in range(0, len(row_records), batch_size):
        batch = row_records[i : i + batch_size]
        texts = [r["text"] for r in batch]
        embeddings = embed_texts(texts)
        milvus_rows = [
            {"chunk_id": r["chunk_id"], "doc_id": r["doc_id"], "text": r["text"], "embedding": emb}
            for r, emb in zip(batch, embeddings) if emb
        ]
        if milvus_rows:
            upsert_sections(milvus_rows)
            total_written += len(milvus_rows)
        logger.info("  batch %d/%d  written=%d", i // batch_size + 1,
                    (len(row_records) + batch_size - 1) // batch_size, total_written)

    return total_written


def main() -> None:
    parser = argparse.ArgumentParser(description="回填 Table 节点结构化字段和行级向量")
    parser.add_argument("--dry-run", action="store_true", help="只打印，不写数据库")
    parser.add_argument("--skip-neo4j", action="store_true")
    parser.add_argument("--skip-milvus", action="store_true")
    args = parser.parse_args()

    if args.dry_run:
        logger.info("=== DRY RUN 模式，不写数据库 ===")

    from src.core.database import get_driver
    driver = get_driver()

    if not args.skip_neo4j:
        n = backfill_neo4j(driver, args.dry_run)
        logger.info("Neo4j 回填完成: %d 节点%s", n, "（dry run）" if args.dry_run else "")

    if not args.skip_milvus:
        n = backfill_milvus(driver, args.dry_run)
        logger.info("Milvus 行级向量回填: %d 条%s", n, "（dry run）" if args.dry_run else "")


if __name__ == "__main__":
    main()
