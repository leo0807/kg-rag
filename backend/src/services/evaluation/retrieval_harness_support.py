from __future__ import annotations

import csv
import io
import json
import re
from datetime import datetime, timezone
from typing import Any

_LIST_SPLIT_RE = re.compile(r"\s*[|,，;；]\s*")
_ALLOWED_STRATEGIES = {"parallel", "sequential", "graph_augmented", "gnn"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_text(value: str) -> str:
    return (value or "").strip()


def normalize_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [normalize_text(str(item)) for item in value if normalize_text(str(item))]

    text = normalize_text(str(value))
    if not text:
        return []

    if text.startswith("[") and text.endswith("]"):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list):
            return [normalize_text(str(item)) for item in parsed if normalize_text(str(item))]

    return [item for item in _LIST_SPLIT_RE.split(text) if item]


def first_present(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        text = normalize_text(str(value))
        if text:
            return text
    return ""


def parse_jsonl_rows(data: bytes) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    text = data.decode("utf-8-sig", errors="replace")
    for idx, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"第 {idx} 行 JSONL 解析失败") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"第 {idx} 行必须是 JSON 对象")
        rows.append(payload)
    return rows


def parse_csv_rows(data: bytes) -> list[dict[str, Any]]:
    text = data.decode("utf-8-sig", errors="replace")
    return list(csv.DictReader(io.StringIO(text)))


def rows_from_upload(filename: str, data: bytes) -> list[dict[str, Any]]:
    lower = filename.lower()
    if lower.endswith(".jsonl"):
        raw_rows = parse_jsonl_rows(data)
    elif lower.endswith(".csv"):
        raw_rows = parse_csv_rows(data)
    else:
        raise ValueError("仅支持 .jsonl 或 .csv 检索评测文件")

    if not raw_rows:
        raise ValueError("评测文件没有可执行的数据行")

    rows: list[dict[str, Any]] = []
    for idx, row in enumerate(raw_rows, start=1):
        question = first_present(row, "question", "问题")
        gold_chunk_ids = normalize_list(
            row.get("gold_chunk_ids")
            or row.get("chunk_ids")
            or row.get("gold_chunks")
            or row.get("标准chunk_ids")
        )
        gold_doc_ids = normalize_list(
            row.get("gold_doc_ids")
            or row.get("doc_ids")
            or row.get("gold_docs")
            or row.get("标准doc_ids")
            or row.get("文档编号")
        )
        if not question:
            continue
        if not gold_chunk_ids and not gold_doc_ids:
            raise ValueError(f"第 {idx} 行缺少 gold_chunk_ids 或 gold_doc_ids")

        row_strategy = first_present(row, "strategy", "检索策略")
        if row_strategy and row_strategy not in _ALLOWED_STRATEGIES:
            raise ValueError(
                f"第 {idx} 行 strategy={row_strategy} 不受支持，仅支持 {sorted(_ALLOWED_STRATEGIES)}",
            )

        rows.append(
            {
                "row_no": idx,
                "question": question,
                "gold_chunk_ids": gold_chunk_ids,
                "gold_doc_ids": gold_doc_ids,
                "domain": first_present(row, "domain", "专业"),
                "strategy": row_strategy,
                "doc_id": first_present(row, "doc_id", "限定文档", "doc_filter"),
            }
        )

    if not rows:
        raise ValueError("评测文件没有可执行的问题行")
    return rows


def unique_doc_ids(sections: list[dict[str, Any]]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for section in sections:
        doc_id = normalize_text(str(section.get("doc_id", "")))
        if doc_id and doc_id not in seen:
            seen.add(doc_id)
            result.append(doc_id)
    return result


def compute_ndcg(retrieved: list[str], gold: list[str], k: int | None = None) -> float:
    """计算 NDCG@K。gold 列表中靠前的元素视为相关性更高（按位置赋权）。"""
    import math
    if not gold:
        return 0.0
    gold_rank: dict[str, float] = {
        item: max(len(gold) - idx, 1) for idx, item in enumerate(gold)
    }
    cut = retrieved[:k] if k else retrieved

    dcg = sum(
        gold_rank[item] / math.log2(rank + 2)
        for rank, item in enumerate(cut)
        if item in gold_rank
    )
    ideal_rels = sorted(gold_rank.values(), reverse=True)[:len(cut) if k else len(gold)]
    idcg = sum(
        rel / math.log2(rank + 2) for rank, rel in enumerate(ideal_rels)
    )
    return round(dcg / idcg, 4) if idcg > 0 else 0.0


def score_against_gold(retrieved: list[str], gold: list[str]) -> tuple[bool, int | None, float, float]:
    if not gold:
        return False, None, 0.0, 0.0

    gold_set = set(gold)
    hit_rank: int | None = None
    matched_items: list[str] = []
    for idx, item in enumerate(retrieved, start=1):
        if item in gold_set:
            if hit_rank is None:
                hit_rank = idx
            if item not in matched_items:
                matched_items.append(item)

    recall = len(matched_items) / max(len(gold_set), 1)
    reciprocal_rank = 1 / hit_rank if hit_rank else 0.0
    return hit_rank is not None, hit_rank, round(recall, 4), round(reciprocal_rank, 4)


def export_rows_to_csv(rows: list[dict[str, Any]]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "row_no", "domain", "strategy", "target_type", "question",
            "matched", "hit_rank", "recall", "reciprocal_rank", "ndcg",
            "gold_chunk_ids", "gold_doc_ids",
            "retrieved_chunk_ids", "retrieved_doc_ids", "source_refs",
        ]
    )
    for row in rows:
        writer.writerow(
            [
                row["row_no"], row["domain"], row["strategy"], row["target_type"],
                row["question"],
                "PASS" if row["matched"] else "FAIL",
                row["hit_rank"] or "",
                row["recall"],
                row["reciprocal_rank"],
                row.get("ndcg", ""),
                " | ".join(row["gold_chunk_ids"]),
                " | ".join(row["gold_doc_ids"]),
                " | ".join(row["retrieved_chunk_ids"]),
                " | ".join(row["retrieved_doc_ids"]),
                " | ".join(row["source_refs"]),
            ]
        )
    return buf.getvalue()
