"""
scripts/attach_orphan_tables.py

将已经存在但未挂到 Section 的 Table 节点，按 page_index/page_start
挂到同一文档中最接近的 Section 上。

用法:
    cd backend/
    .venv/bin/python scripts/attach_orphan_tables.py [--dry-run]
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.database import get_driver, init_db
from src.core.logging import setup_logging


setup_logging()
log = logging.getLogger(__name__)


def get_orphan_tables(driver) -> list[dict]:
    with driver.session() as session:
        result = session.run(
            """
            MATCH (t:Table)
            WHERE NOT (t)<-[:HAS_TABLE]-(:Section)
            RETURN t.doc_id AS doc_id,
                   t.table_id AS table_id,
                   coalesce(t.page_start, t.page_index, 0) AS page_num
            ORDER BY doc_id, page_num, table_id
            """
        )
        return [dict(r) for r in result]


def get_sections(driver, doc_id: str) -> list[dict]:
    with driver.session() as session:
        result = session.run(
            """
            MATCH (d:Document {name: $doc_id})-[:HAS_SECTION]->(s:Section)
            RETURN s.chunk_id AS chunk_id,
                   coalesce(s.page_idx, 0) AS page_idx,
                   coalesce(s.seq_index, 0) AS seq_index
            ORDER BY page_idx, seq_index
            """,
            doc_id=doc_id,
        )
        return [dict(r) for r in result]


def attach_table(driver, table_id: str, chunk_id: str, dry_run: bool = False) -> None:
    if dry_run:
        return
    with driver.session() as session:
        result = session.run(
            """
            MATCH (sec:Section {chunk_id: $chunk_id})
            MATCH (t:Table {table_id: $table_id})
            MERGE (sec)-[:HAS_TABLE]->(t)
            RETURN count(*) AS affected
            """,
            chunk_id=chunk_id,
            table_id=table_id,
        )
        result.consume()


def pick_section(sections: list[dict], page_num: int) -> str | None:
    if not sections:
        return None
    best = min(
        sections,
        key=lambda s: (
            abs(int(s["page_idx"]) - int(page_num)),
            int(s["seq_index"]),
        ),
    )
    return best["chunk_id"]


def main() -> None:
    parser = argparse.ArgumentParser(description="把孤儿 Table 挂回最近的 Section")
    parser.add_argument("--dry-run", action="store_true", help="只打印，不写入 Neo4j")
    args = parser.parse_args()

    init_db()
    driver = get_driver()

    orphans = get_orphan_tables(driver)
    if not orphans:
        print("没有发现孤儿 Table。")
        return

    total = len(orphans)
    print(f"发现 {total} 个孤儿 Table{'（DRY-RUN）' if args.dry_run else ''}")

    attached = skipped = 0
    section_cache: dict[str, list[dict]] = {}
    current_doc = ""
    current_sections: list[dict] = []

    for i, item in enumerate(orphans, 1):
        doc_id = item["doc_id"]
        if doc_id != current_doc:
            current_doc = doc_id
            current_sections = section_cache.get(doc_id) or get_sections(driver, doc_id)
            section_cache[doc_id] = current_sections

        chunk_id = pick_section(current_sections, int(item["page_num"] or 0))
        print(f"[{i}/{total}] {doc_id}:{item['table_id']} -> {chunk_id or 'SKIP'}", end="  ", flush=True)
        if not chunk_id:
            print("— 无 Section")
            skipped += 1
            continue

        attach_table(driver, item["table_id"], chunk_id, dry_run=args.dry_run)
        print("✓")
        attached += 1

    print(f"\n完成：attached={attached}, skipped={skipped}")


if __name__ == "__main__":
    main()
