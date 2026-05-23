from __future__ import annotations

import json

from src.services.tables.canonicalization import canonicalize_table_fragments


def _table(table_id: str, page_index: int, rows: list[list[str]], chunk_id: str = "CPS0100_1") -> dict:
    return {
        "table_id": table_id,
        "chunk_id": chunk_id,
        "doc_id": "CPS0100",
        "page_index": page_index,
        "markdown": "",
        "rows_json": json.dumps(rows, ensure_ascii=False),
        "constraints": [],
    }


def test_canonicalize_table_fragments_merges_consecutive_pages_with_same_header():
    merged = canonicalize_table_fragments(
        [
            _table(
                "CPS0100_tbl_0",
                3,
                [["参数", "值"], ["厚度", "2mm"]],
            ),
            _table(
                "CPS0100_tbl_1",
                4,
                [["参数", "值"], ["强度", "高"]],
            ),
        ],
    )

    assert len(merged) == 1
    assert merged[0]["page_start"] == 3
    assert merged[0]["page_end"] == 4
    assert merged[0]["page_indices"] == [3, 4]
    assert merged[0]["fragment_count"] == 2
    assert "强度" in merged[0]["markdown"]


def test_canonicalize_table_fragments_keeps_non_consecutive_tables_separate():
    merged = canonicalize_table_fragments(
        [
            _table("CPS0100_tbl_0", 3, [["参数", "值"], ["厚度", "2mm"]]),
            _table("CPS0100_tbl_1", 5, [["参数", "值"], ["强度", "高"]]),
        ],
    )

    assert len(merged) == 2
