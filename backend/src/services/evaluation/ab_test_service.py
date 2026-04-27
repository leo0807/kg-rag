from __future__ import annotations

import asyncio
import uuid
from typing import Any

from neo4j import Driver

from .retrieval_harness_support import (
    _ALLOWED_STRATEGIES,
    compute_ndcg,
    normalize_text,
    now as _now,
    rows_from_upload,
    score_against_gold,
    unique_doc_ids,
)

_tasks: dict[str, dict[str, Any]] = {}
_DO_RETRIEVAL: Any | None = None


def _get_do_retrieval():
    global _DO_RETRIEVAL
    if callable(_DO_RETRIEVAL):
        return _DO_RETRIEVAL
    from ...routers.query.core import do_retrieval
    _DO_RETRIEVAL = do_retrieval
    return do_retrieval


async def _run_ab_task(
    task_id: str,
    rows: list[dict[str, Any]],
    strategies: list[str],
    top_k: int,
    driver: Driver,
) -> None:
    task = _tasks[task_id]
    task["status"] = "running"
    task["started_at"] = _now()

    per_strategy: dict[str, list[dict[str, Any]]] = {s: [] for s in strategies}
    total_rows = len(rows)
    processed = 0

    try:
        for row in rows:
            task["current_question"] = row["question"][:120]
            do_retrieval = _get_do_retrieval()

            for strategy in strategies:
                row_strategy = row["strategy"] or strategy
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
                    normalize_text(str(s.get("chunk_id", "")))
                    for s in retrieved_sections
                    if normalize_text(str(s.get("chunk_id", "")))
                ]
                retrieved_doc_ids = unique_doc_ids(retrieved_sections)

                target_type = "chunk" if row["gold_chunk_ids"] else "doc"
                gold = row["gold_chunk_ids"] if target_type == "chunk" else row["gold_doc_ids"]
                retrieved = retrieved_chunk_ids if target_type == "chunk" else retrieved_doc_ids

                hit, hit_rank, recall, rr = score_against_gold(retrieved, gold)
                ndcg = compute_ndcg(retrieved, gold, k=top_k)

                per_strategy[strategy].append({
                    "row_no": row["row_no"],
                    "question": row["question"],
                    "domain": row["domain"],
                    "strategy": strategy,
                    "target_type": target_type,
                    "matched": hit,
                    "hit_rank": hit_rank,
                    "recall": recall,
                    "reciprocal_rank": rr,
                    "ndcg": ndcg,
                })

            processed += 1
            task["completed"] = processed
            await asyncio.sleep(0)

        strategy_summaries: list[dict[str, Any]] = []
        for strategy, results in per_strategy.items():
            total = len(results)
            matched = sum(1 for r in results if r["matched"])
            strategy_summaries.append({
                "strategy": strategy,
                "total": total,
                "matched": matched,
                "hit_rate": round(matched / max(total, 1), 4),
                "avg_recall": round(sum(r["recall"] for r in results) / max(total, 1), 4),
                "mrr": round(sum(r["reciprocal_rank"] for r in results) / max(total, 1), 4),
                "avg_ndcg": round(sum(r["ndcg"] for r in results) / max(total, 1), 4),
                "results": results,
            })

        strategy_summaries.sort(key=lambda x: x["avg_ndcg"], reverse=True)

        task["status"] = "completed"
        task["finished_at"] = _now()
        task["strategy_summaries"] = strategy_summaries
        task["summary"] = {
            "total_questions": total_rows,
            "strategies_compared": len(strategies),
            "winner": strategy_summaries[0]["strategy"] if strategy_summaries else "",
            "details": [
                {k: v for k, v in s.items() if k != "results"}
                for s in strategy_summaries
            ],
        }
    except Exception as exc:
        task["status"] = "failed"
        task["finished_at"] = _now()
        task["error"] = str(exc)


async def start_ab_test(
    filename: str,
    data: bytes,
    strategies: list[str],
    top_k: int,
    driver: Driver,
) -> dict[str, Any]:
    invalid = [s for s in strategies if s not in _ALLOWED_STRATEGIES]
    if invalid:
        raise ValueError(f"不支持的策略: {invalid}，仅支持 {sorted(_ALLOWED_STRATEGIES)}")
    if len(strategies) < 2:
        raise ValueError("A/B 测试至少需要 2 个策略")

    rows = rows_from_upload(filename, data)
    task_id = uuid.uuid4().hex
    _tasks[task_id] = {
        "task_id": task_id,
        "filename": filename,
        "status": "queued",
        "strategies": strategies,
        "top_k": top_k,
        "created_at": _now(),
        "started_at": None,
        "finished_at": None,
        "total": len(rows),
        "completed": 0,
        "current_question": "",
        "error": "",
        "summary": None,
        "strategy_summaries": [],
    }
    asyncio.create_task(_run_ab_task(task_id, rows, strategies, top_k, driver))
    return get_ab_task(task_id)


def get_ab_task(task_id: str) -> dict[str, Any]:
    task = _tasks.get(task_id)
    if not task:
        raise KeyError(task_id)
    return task


def list_ab_tasks(limit: int = 20) -> list[dict[str, Any]]:
    rows = sorted(
        _tasks.values(),
        key=lambda t: str(t.get("finished_at") or t.get("started_at") or t.get("created_at") or ""),
        reverse=True,
    )
    return rows[: max(limit, 1)]


def export_ab_csv(task_id: str) -> str:
    import csv, io
    task = get_ab_task(task_id)
    if task["status"] != "completed":
        raise ValueError("任务尚未完成，暂时不能导出")

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["strategy", "row_no", "question", "domain", "target_type",
                     "matched", "hit_rank", "recall", "reciprocal_rank", "ndcg"])
    for summary in task["strategy_summaries"]:
        for row in summary["results"]:
            writer.writerow([
                row["strategy"], row["row_no"], row["question"], row["domain"],
                row["target_type"],
                "PASS" if row["matched"] else "FAIL",
                row["hit_rank"] or "",
                row["recall"], row["reciprocal_rank"], row["ndcg"],
            ])
    return buf.getvalue()
