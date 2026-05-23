"""Canonicalize extracted table fragments into logical tables."""

from __future__ import annotations

import json
import re
from copy import deepcopy

from .normalization import rows_to_constraints, rows_to_markdown

_SPACE_RE = re.compile(r"\s+")


def _normalize_cell(value) -> str:
    return _SPACE_RE.sub(" ", str(value or "").strip()).lower()


def _parse_rows(table: dict) -> list[list[str]]:
    try:
        rows = json.loads(table.get("rows_json") or "[]")
    except Exception:
        rows = []
    if not isinstance(rows, list):
        return []
    normalized: list[list[str]] = []
    for row in rows:
        if not isinstance(row, list):
            continue
        clean = [str(cell or "").strip() for cell in row]
        if any(clean):
            normalized.append(clean)
    return normalized


def _header_signature(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    return "\u241f".join(_normalize_cell(cell) for cell in rows[0])


def _page_index(table: dict) -> int:
    try:
        return int(table.get("page_index") or 0)
    except Exception:
        return 0


def _page_indices(table: dict) -> list[int]:
    raw = table.get("page_indices")
    if isinstance(raw, list) and raw:
        indices = []
        for value in raw:
            try:
                indices.append(int(value))
            except Exception:
                continue
        if indices:
            return sorted(set(indices))
    return [_page_index(table)]


def _normalise_table(table: dict) -> dict:
    rows = _parse_rows(table)
    page_indices = _page_indices(table)
    normalized = deepcopy(table)
    normalized["_rows"] = rows
    normalized["_header_sig"] = _header_signature(rows)
    normalized["page_indices"] = page_indices
    normalized["page_start"] = min(page_indices) if page_indices else _page_index(table)
    normalized["page_end"] = max(page_indices) if page_indices else _page_index(table)
    normalized["page_index"] = normalized["page_start"]
    normalized["fragment_count"] = int(table.get("fragment_count") or len(page_indices) or 1)
    if rows:
        normalized["markdown"] = rows_to_markdown(rows)
        normalized["rows_json"] = json.dumps(rows, ensure_ascii=False)
        normalized["constraints"] = rows_to_constraints(
            rows,
            normalized.get("chunk_id", ""),
            normalized.get("doc_id", ""),
            normalized.get("table_id", ""),
        )
    else:
        normalized["constraints"] = list(table.get("constraints") or [])
    return normalized


def _can_merge(prev: dict, current: dict) -> bool:
    if prev.get("doc_id") != current.get("doc_id"):
        return False
    if prev.get("chunk_id") != current.get("chunk_id"):
        return False
    if prev.get("_header_sig") != current.get("_header_sig"):
        return False
    if _page_index(current) != int(prev.get("page_end") or 0) + 1:
        return False
    return True


def _merge_tables(prev: dict, current: dict) -> dict:
    merged = deepcopy(prev)
    prev_rows = prev.get("_rows") or []
    curr_rows = current.get("_rows") or []
    if curr_rows and prev.get("_header_sig") == current.get("_header_sig"):
        curr_rows = curr_rows[1:]
    rows = [*prev_rows, *curr_rows]
    page_indices = sorted(set((prev.get("page_indices") or []) + (current.get("page_indices") or [])))
    merged["page_indices"] = page_indices
    merged["page_start"] = min(page_indices) if page_indices else prev.get("page_start", 0)
    merged["page_end"] = max(page_indices) if page_indices else prev.get("page_end", 0)
    merged["page_index"] = merged["page_start"]
    merged["fragment_count"] = int(prev.get("fragment_count") or 1) + int(current.get("fragment_count") or 1)
    merged["_rows"] = rows
    merged["_header_sig"] = prev.get("_header_sig", "")
    if rows:
        merged["markdown"] = rows_to_markdown(rows)
        merged["rows_json"] = json.dumps(rows, ensure_ascii=False)
    merged["constraints"] = rows_to_constraints(
        rows,
        merged.get("chunk_id", ""),
        merged.get("doc_id", ""),
        merged.get("table_id", ""),
    )
    return merged


def canonicalize_table_fragments(table_data: list[dict]) -> list[dict]:
    if not table_data:
        return []

    prepared = [_normalise_table(table) for table in table_data]
    prepared.sort(
        key=lambda table: (
            str(table.get("doc_id") or ""),
            str(table.get("chunk_id") or ""),
            int(table.get("page_start") or 0),
            str(table.get("table_id") or ""),
        ),
    )

    merged: list[dict] = []
    for table in prepared:
        if merged and _can_merge(merged[-1], table):
            merged[-1] = _merge_tables(merged[-1], table)
        else:
            merged.append(table)

    for table in merged:
        table.pop("_rows", None)
        table.pop("_header_sig", None)
    return merged
