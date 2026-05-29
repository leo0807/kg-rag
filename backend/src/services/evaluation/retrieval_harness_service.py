from __future__ import annotations

import asyncio
import uuid
from typing import Any

from neo4j import Driver
from .retrieval_harness_support import (
    _ALLOWED_STRATEGIES,
    compute_ndcg,
    export_rows_to_csv,
    normalize_text,
    now as _now,
    rows_from_upload,
    score_against_gold,
    unique_doc_ids,
)
from ..infra.task_state import TaskState, get_task_state_store

_STORE_PREFIX = "eval:retrieval:"
_store = get_task_state_store()
DO_RETRIEVAL: Any | None = None


def _get_do_retrieval():
    global DO_RETRIEVAL
    if callable(DO_RETRIEVAL):
        return DO_RETRIEVAL

    from ...routers.query.core import do_retrieval

    DO_RETRIEVAL = do_retrieval
    return do_retrieval


def _rows_from_upload(filename: str, data: bytes) -> list[dict[str, Any]]:
    return rows_from_upload(filename, data)


async def _run_task(
    task_id: str,
    rows: list[dict[str, Any]],
    strategy: str,
    top_k: int,
    driver: Driver,
) -> None:
    key = f"{_STORE_PREFIX}{task_id}"
    _state = _store.get(key)
    task = _state.progress if _state else {}
    task["status"] = "running"
    task["started_at"] = _now()
    _store.update(key, status="running", progress=task)

    results: list[dict[str, Any]] = []

    try:
        for idx, row in enumerate(rows, start=1):
            task["current_question"] = row["question"][:120]

            row_strategy = row["strategy"] or strategy
            do_retrieval = _get_do_retrieval()
            sections, _, _ = await asyncio.to_thread(
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
                normalize_text(str(section.get("chunk_id", "")))
                for section in retrieved_sections
                if normalize_text(str(section.get("chunk_id", "")))
            ]
            retrieved_doc_ids = unique_doc_ids(retrieved_sections)
            source_refs = [
                f"{section.get('doc_id', '')} §{section.get('number', '')}".strip()
                for section in retrieved_sections
                if section.get("doc_id") and section.get("number")
            ]

            chunk_hit, chunk_rank, chunk_recall, chunk_rr = score_against_gold(
                retrieved_chunk_ids,
                row["gold_chunk_ids"],
            )
            doc_hit, doc_rank, doc_recall, doc_rr = score_against_gold(
                retrieved_doc_ids,
                row["gold_doc_ids"],
            )

            target_type = "chunk" if row["gold_chunk_ids"] else "doc"
            matched = chunk_hit if target_type == "chunk" else doc_hit
            hit_rank = chunk_rank if target_type == "chunk" else doc_rank
            recall = chunk_recall if target_type == "chunk" else doc_recall
            reciprocal_rank = chunk_rr if target_type == "chunk" else doc_rr
            ndcg = compute_ndcg(
                retrieved_chunk_ids if target_type == "chunk" else retrieved_doc_ids,
                row["gold_chunk_ids"] if target_type == "chunk" else row["gold_doc_ids"],
                k=top_k,
            )

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
                "ndcg": ndcg,
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
            _store.update(key, progress=task)
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
            "avg_ndcg": round(
                sum(float(row.get("ndcg", 0)) for row in results) / max(total, 1),
                4,
            ),
            "chunk_target_count": chunk_target_count,
            "doc_target_count": doc_target_count,
        }
        _store.update(key, status="completed", progress=task)
    except Exception as exc:
        task["status"] = "failed"
        task["finished_at"] = _now()
        task["error"] = str(exc)
        _store.update(key, status="failed", progress=task)


async def start_retrieval_harness(
    filename: str,
    data: bytes,
    strategy: str,
    top_k: int,
    driver: Driver,
) -> dict[str, Any]:
    if strategy not in _ALLOWED_STRATEGIES:
        raise ValueError(f"仅支持 {sorted(_ALLOWED_STRATEGIES)} 检索策略")

    rows = rows_from_upload(filename, data)
    task_id = uuid.uuid4().hex
    key = f"{_STORE_PREFIX}{task_id}"
    initial_progress = {
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
    _store.set(key, TaskState(task_id=task_id, status="queued", progress=initial_progress))
    asyncio.create_task(_run_task(task_id, rows, strategy, top_k, driver))
    return get_retrieval_task(task_id)


def get_retrieval_task(task_id: str) -> dict[str, Any]:
    key = f"{_STORE_PREFIX}{task_id}"
    state = _store.get(key)
    if state is None:
        raise KeyError(task_id)
    return state.progress


def list_retrieval_tasks(limit: int = 20) -> list[dict[str, Any]]:
    states = _store.list_by_prefix(_STORE_PREFIX, limit=max(limit, 1))
    return [s.progress for s in states]


def export_retrieval_task_csv(task_id: str) -> str:
    task = get_retrieval_task(task_id)
    if task["status"] != "completed":
        raise ValueError("任务尚未完成，暂时不能导出")

    return export_rows_to_csv(task["results"])
