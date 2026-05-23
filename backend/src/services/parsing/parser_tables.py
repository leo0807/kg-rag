from __future__ import annotations

import logging
import pdfplumber
from pathlib import Path

from .parser_heading import _extract_page_tables
from ..tables.canonicalization import canonicalize_table_fragments

logger = logging.getLogger(__name__)


def _rows_to_markdown(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    rows = [(r + [""] * (width - len(r)))[:width] for r in rows]
    header = "| " + " | ".join(rows[0]) + " |"
    sep    = "| " + " | ".join("---" for _ in rows[0]) + " |"
    body   = "\n".join("| " + " | ".join(str(c) for c in r) + " |" for r in rows[1:])
    return f"{header}\n{sep}\n{body}" if body else f"{header}\n{sep}"


def extract_tables_pdfplumber(pdf_path: Path, doc_id: str, sections: list[dict]) -> list[dict]:
    import json as _json

    page_to_chunk: dict[int, str] = {}
    for s in sections:
        pi = s.get("page_idx")
        if pi is not None and pi not in page_to_chunk:
            page_to_chunk[pi] = s["chunk_id"]
    fallback_chunk = sections[0]["chunk_id"] if sections else f"{doc_id}_1"

    tables: list[dict] = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            table_seq = 0
            for page_idx, page in enumerate(pdf.pages):
                for table in _extract_page_tables(page):
                    rows = table.get("rows") or []
                    if not rows:
                        continue
                    rows = [[str(cell or "").strip() for cell in row] for row in rows]
                    rows = [r for r in rows if any(c for c in r)]
                    if len(rows) < 2:
                        continue
                    markdown = _rows_to_markdown(rows)
                    rows_json = _json.dumps(rows, ensure_ascii=False)
                    chunk_id = page_to_chunk.get(page_idx)
                    if chunk_id is None:
                        for pi in range(page_idx - 1, -1, -1):
                            if pi in page_to_chunk:
                                chunk_id = page_to_chunk[pi]
                                break
                    chunk_id = chunk_id or fallback_chunk
                    tables.append({
                        "table_id":   f"{doc_id}_tbl_{table_seq}",
                        "chunk_id":   chunk_id,
                        "markdown":   markdown,
                        "rows_json":  rows_json,
                        "page_index": page_idx,
                        "row_count":  max(0, len(rows) - 1),
                        "bbox":       table.get("bbox"),
                        "constraints": [],
                    })
                    table_seq += 1
    except Exception as e:
        logger.warning("pdfplumber 表格提取失败 %s: %s", pdf_path.name, e)

    return canonicalize_table_fragments(tables)
