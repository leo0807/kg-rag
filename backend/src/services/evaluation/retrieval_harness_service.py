from __future__ import annotations

import asyncio
import csv
import io
import json
import re
import uuid
from datetime import datetime
from typing import Any

from neo4j import Driver

_tasks: dict[str, dict[str, Any]] = {}
_LIST_SPLIT_RE = re.compile(r"\s*[|,，;；]\s*")
_ALLOWED_STRATEGIES = {"parallel", "sequential", "graph_augmented", "gnn"}
DO_RETRIEVAL: Any | None = None


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _normalize_text(value: str) -> str:
    return (value or "").strip()


def _get_do_retrieval():
    global DO_RETRIEVAL
    if callable(DO_RETRIEVAL):
        return DO_RETRIEVAL

    from ...routers.query.core import do_retrieval

    DO_RETRIEVAL = do_retrieval
    return do_retrieval


def _normalize_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [_normalize_text(str(item)) for item in value if _normalize_text(str(item))]

    text = _normalize_text(str(value))
    if not text:
        return []

    if text.startswith("[") and text.endswith("]"):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list):
            return [_normalize_text(str(item)) for item in parsed if _normalize_text(str(item))]

    return [item for item in _LIST_SPLIT_RE.split(text) if item]


def _first_present(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        text = _normalize_text(str(value))
        if text:
            return text
    return ""


def _parse_jsonl_rows(data: bytes) -> list[dict[str, Any]]:
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


def _parse_csv_rows(data: bytes) -> list[dict[str, Any]]:
    text = data.decode("utf-8-sig", errors="replace")
    return list(csv.DictReader(io.StringIO(text)))


def _rows_from_upload(filename: str, data: bytes) -> list[dict[str, Any]]:
    lower = filename.lower()
    if lower.endswith(".jsonl"):
        raw_rows = _parse_jsonl_rows(data)
    elif lower.endswith(".csv"):
        raw_rows = _parse_csv_rows(data)
    else:
        raise ValueError("仅支持 .jsonl 或 .csv 检索评测文件")

    if not raw_rows:
        raise ValueError("评测文件没有可执行的数据行")

    rows: list[dict[str, Any]] = []
    for idx, row in enumerate(raw_rows, start=1):
        question = _first_present(row, "question", "问题")
        gold_chunk_ids = _normalize_list(
            row.get("gold_chunk_ids")
            or row.get("chunk_ids")
            or row.get("gold_chunks")
            or row.get("标准chunk_ids")
        )
        gold_doc_ids = _normalize_list(
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

        row_strategy = _first_present(row, "strategy", "检索策略")
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
                "domain": _first_present(row, "domain", "专业"),
                "strategy": row_strategy,
                "doc_id": _first_present(row, "doc_id", "限定文档", "doc_filter"),
            },
        )

    if not rows:
        raise ValueError("评测文件没有可执行的问题行")
    return rows


def _unique_doc_ids(sections: list[dict[str, Any]]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for section in sections:
        doc_id = _normalize_text(str(section.get("doc_id", "")))
        if doc_id and doc_id not in seen:
            seen.add(doc_id)
            result.append(doc_id)
    return result


def _score_against_gold(retrieved: list[str], gold: list[str]) -> tuple[bool, int | None, float, float]:
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


async def _run_task(
    task_id: str,
    rows: list[dict[str, Any]],
    strategy: str,
    top_k: int,
    driver: Driver,
) -> None:
    task = _tasks[task_id]
    task["status"] = "running"
    task["started_at"] = _now()

    results: list[dict[str, Any]] = []

    try:
        for idx, row in enumerate(rows, start=1):
            task["current_question"] = row["question"][:120]

            row_strategy = row["strategy"] or strategy
            do_retrieval = _get_do_retrieval()
            sections, _ = await asyncio.to_thread(
                do_retrieval,
                driver,
                row["question"],
                row_strategy,
                top_k,
                False,
                0.5,
                row["doc_id"],
            )

            retrieved_sections = sections[:top_k]
            retrieved_chunk_ids = [
                _normalize_text(str(section.get("chunk_id", "")))
                for section in retrieved_sections
                if _normalize_text(str(section.get("chunk_id", "")))
            ]
            retrieved_doc_ids = _unique_doc_ids(retrieved_sections)
            source_refs = [
                f"{section.get('doc_id', '')} §{section.get('number', '')}".strip()
                for section in retrieved_sections
                if section.get("doc_id") and section.get("number")
            ]

            chunk_hit, chunk_rank, chunk_recall, chunk_rr = _score_against_gold(
                retrieved_chunk_ids,
                row["gold_chunk_ids"],
            )
            doc_hit, doc_rank, doc_recall, doc_rr = _score_against_gold(
                retrieved_doc_ids,
                row["gold_doc_ids"],
            )

            target_type = "chunk" if row["gold_chunk_ids"] else "doc"
            matched = chunk_hit if target_type == "chunk" else doc_hit
            hit_rank = chunk_rank if target_type == "chunk" else doc_rank
            recall = chunk_recall if target_type == "chunk" else doc_recall
            reciprocal_rank = chunk_rr if target_type == "chunk" else doc_rr

            result_row = {
                "row_no": row["row_no"],
                "question": row["question"],
                "domain": row["domain"],
                "strategy": row_strategy,
                "target_type": target_type,
                "gold_chunk_ids": row["gold_chunk_ids"],
                "gold_doc_ids": row["gold_doc_ids"],
                "retrieved_chunk_ids": retrieved_chunk_ids,
                "retrieved_doc_ids": retrieved_doc_ids,
                "matched": matched,
                "hit_rank": hit_rank,
                "recall": recall,
                "reciprocal_rank": reciprocal_rank,
                "chunk_hit": chunk_hit,
                "chunk_hit_rank": chunk_rank,
                "chunk_recall": chunk_recall,
                "chunk_mrr": chunk_rr,
                "doc_hit": doc_hit,
                "doc_hit_rank": doc_rank,
                "doc_recall": doc_recall,
                "doc_mrr": doc_rr,
                "source_refs": source_refs,
            }
            results.append(result_row)

            task["completed"] = idx
            task["matched"] = sum(1 for item in results if item["matched"])
            task["unmatched"] = idx - task["matched"]
            task["results_preview"] = results[-20:]
            await asyncio.sleep(0)

        total = len(results)
        chunk_target_count = sum(1 for row in results if row["target_type"] == "chunk")
        doc_target_count = total - chunk_target_count
        task["status"] = "completed"
        task["finished_at"] = _now()
        task["results"] = results
        task["results_preview"] = results[:50]
        task["summary"] = {
            "total": total,
            "matched": task["matched"],
            "unmatched": task["unmatched"],
            "hit_rate": round(task["matched"] / max(total, 1), 4),
            "avg_recall": round(
                sum(float(row["recall"]) for row in results) / max(total, 1),
                4,
            ),
            "mrr": round(
                sum(float(row["reciprocal_rank"]) for row in results) / max(total, 1),
                4,
            ),
            "chunk_target_count": chunk_target_count,
            "doc_target_count": doc_target_count,
        }
    except Exception as exc:
        task["status"] = "failed"
        task["finished_at"] = _now()
        task["error"] = str(exc)


async def start_retrieval_harness(
    filename: str,
    data: bytes,
    strategy: str,
    top_k: int,
    driver: Driver,
) -> dict[str, Any]:
    if strategy not in _ALLOWED_STRATEGIES:
        raise ValueError(f"仅支持 {sorted(_ALLOWED_STRATEGIES)} 检索策略")

    rows = _rows_from_upload(filename, data)
    task_id = uuid.uuid4().hex
    _tasks[task_id] = {
        "task_id": task_id,
        "filename": filename,
        "status": "queued",
        "strategy": strategy,
        "top_k": top_k,
        "created_at": _now(),
        "started_at": None,
        "finished_at": None,
        "total": len(rows),
        "completed": 0,
        "matched": 0,
        "unmatched": 0,
        "current_question": "",
        "error": "",
        "summary": None,
        "results_preview": [],
        "results": [],
    }
    asyncio.create_task(_run_task(task_id, rows, strategy, top_k, driver))
    return get_retrieval_task(task_id)


def get_retrieval_task(task_id: str) -> dict[str, Any]:
    task = _tasks.get(task_id)
    if not task:
        raise KeyError(task_id)
    return task


def list_retrieval_tasks(limit: int = 20) -> list[dict[str, Any]]:
    rows = sorted(
        _tasks.values(),
        key=lambda task: str(task.get("finished_at") or task.get("started_at") or task.get("created_at") or ""),
        reverse=True,
    )
    return rows[: max(limit, 1)]


def export_retrieval_task_csv(task_id: str) -> str:
    task = get_retrieval_task(task_id)
    if task["status"] != "completed":
        raise ValueError("任务尚未完成，暂时不能导出")

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "row_no",
            "domain",
            "strategy",
            "target_type",
            "question",
            "matched",
            "hit_rank",
            "recall",
            "reciprocal_rank",
            "gold_chunk_ids",
            "gold_doc_ids",
            "retrieved_chunk_ids",
            "retrieved_doc_ids",
            "source_refs",
        ],
    )
    for row in task["results"]:
        writer.writerow(
            [
                row["row_no"],
                row["domain"],
                row["strategy"],
                row["target_type"],
                row["question"],
                "PASS" if row["matched"] else "FAIL",
                row["hit_rank"] or "",
                row["recall"],
                row["reciprocal_rank"],
                " | ".join(row["gold_chunk_ids"]),
                " | ".join(row["gold_doc_ids"]),
                " | ".join(row["retrieved_chunk_ids"]),
                " | ".join(row["retrieved_doc_ids"]),
                " | ".join(row["source_refs"]),
            ],
        )
    return buf.getvalue()
