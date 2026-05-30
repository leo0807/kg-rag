from __future__ import annotations

import csv
import io
import logging
import uuid
from datetime import datetime
from typing import Any

from neo4j import Driver
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from ...db.models import ObjectiveDocEvalTask
from .objective_doc_eval_parser import extract_objective_questions
from .objective_doc_source_detection import resolve_source_doc_id

from ..infra.task_state import TaskState, get_task_state_store

logger = logging.getLogger(__name__)

_STORE_PREFIX = "eval:objective_doc:"
_store = get_task_state_store()


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _task_snapshot(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_id": task.get("task_id", ""),
        "filename": task.get("filename", ""),
        "source_doc_id": task.get("source_doc_id", ""),
        "strategy": task.get("strategy", "parallel"),
        "top_k": int(task.get("top_k", 5) or 5),
        "status": task.get("status", "queued"),
        "total": int(task.get("total", 0) or 0),
        "completed": int(task.get("completed", 0) or 0),
        "current_question": task.get("current_question", ""),
        "error": task.get("error", ""),
        "summary": task.get("summary"),
        "results": task.get("results"),
        "started_at": task.get("started_at"),
        "finished_at": task.get("finished_at"),
    }


async def _persist_task(task: dict[str, Any]) -> None:
    _tid = (task or {}).get("task_id", "")
    if _tid:
        _store.update(f"{_STORE_PREFIX}{_tid}", status=task.get("status", ""), progress=task)

    from ...db.session import AsyncSessionLocal, init_tables

    payload = _task_snapshot(task)

    async def _write_once() -> None:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(ObjectiveDocEvalTask).where(ObjectiveDocEvalTask.task_id == payload["task_id"])
            )
            row = result.scalar_one_or_none()
            if row is None:
                row = ObjectiveDocEvalTask(**payload)
                db.add(row)
            else:
                for key, value in payload.items():
                    setattr(row, key, value)
            await db.commit()

    try:
        await _write_once()
    except SQLAlchemyError as exc:
        logger.warning("客观题评测结果落库失败，尝试自动初始化表后重试: %s", exc)
        try:
            await init_tables()
            await _write_once()
        except Exception as retry_exc:
            logger.exception("客观题评测结果落库仍然失败: %s", retry_exc)
    except Exception as exc:
        logger.exception("客观题评测结果落库异常: %s", exc)


def _task_from_row(row: ObjectiveDocEvalTask) -> dict[str, Any]:
    return {
        "task_id": row.task_id,
        "filename": row.filename,
        "source_doc_id": row.source_doc_id or "",
        "status": row.status,
        "strategy": row.strategy,
        "top_k": row.top_k,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "started_at": row.started_at,
        "finished_at": row.finished_at,
        "total": row.total,
        "completed": row.completed,
        "current_question": row.current_question or "",
        "error": row.error or "",
        "summary": row.summary,
        "results_preview": (row.results or [])[:50],
        "results": row.results or [],
    }


async def _load_task_from_db(task_id: str) -> dict[str, Any]:
    from ...db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ObjectiveDocEvalTask).where(ObjectiveDocEvalTask.task_id == task_id)
        )
        row = result.scalar_one_or_none()
        if not row:
            raise KeyError(task_id)
        return _task_from_row(row)


async def list_objective_task_records(limit: int = 20) -> list[dict[str, Any]]:
    from ...db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ObjectiveDocEvalTask)
            .order_by(ObjectiveDocEvalTask.created_at.desc())
            .limit(max(limit, 1))
        )
        rows = result.scalars().all()
        return [_task_from_row(row) for row in rows]


async def start_objective_doc_eval(
    filename: str,
    data: bytes,
    strategy: str,
    top_k: int,
    driver: Driver,
    source_doc_id: str = "",
    doc_id: str = "",
) -> dict[str, Any]:
    task_id = uuid.uuid4().hex
    task: dict[str, Any] = {
        "task_id": task_id, "filename": filename, "status": "queued",
        "strategy": strategy, "top_k": top_k,
        "source_doc_id": source_doc_id or "", "doc_id": doc_id or "",
        "created_at": _now(),
        "started_at": None, "finished_at": None,
        "total": 0, "completed": 0,
        "current_question": "正在解析文档...", "error": "", "summary": None,
        "results_preview": [], "results": [],
    }
    _store.set(f"{_STORE_PREFIX}{task_id}", TaskState(task_id=task_id, status="queued", progress=task))
    await _persist_task(task)
    try:
        questions = extract_objective_questions(filename, data)
        resolved_source_doc_id = resolve_source_doc_id(
            filename,
            questions,
            source_doc_id=source_doc_id,
            legacy_doc_id=doc_id,
        )
        task["source_doc_id"] = resolved_source_doc_id
        task["doc_id"] = resolved_source_doc_id
        task["total"] = len(questions)
        task["current_question"] = f"题目解析完成，准备评测 {len(questions)} 题"
        await _persist_task(task)
        if resolved_source_doc_id:
            from .objective_doc_source_detection import baseline_retrieval_hit_rate

            hit_rate, _ = baseline_retrieval_hit_rate(questions, resolved_source_doc_id, strategy, top_k, driver)
            if hit_rate < 0.5:
                task["status"] = "failed"
                task["finished_at"] = _now()
                task["error"] = f"基线命中率 {hit_rate:.0%} 过低，请检查 source_doc_id 设置"
                task["current_question"] = f"基线检索未通过：{resolved_source_doc_id}"
                await _persist_task(task)
                return get_objective_task(task_id)
    except Exception as exc:
        task["status"] = "failed"
        task["finished_at"] = _now()
        task["error"] = f"{type(exc).__name__}: {exc}"
        task["current_question"] = "文档解析失败"
        await _persist_task(task)
        raise ValueError(str(exc)) from exc

    from ...tasks.quality_tasks import run_objective_doc_eval
    run_objective_doc_eval.delay(task_id=task_id, questions=questions, strategy=strategy, top_k=top_k)
    return get_objective_task(task_id)


def get_objective_task(task_id: str) -> dict[str, Any]:
    state = _store.get(f"{_STORE_PREFIX}{task_id}")
    if state is None:
        raise KeyError(task_id)
    return state.progress


def list_objective_eval_tasks(limit: int = 20) -> list[dict[str, Any]]:
    rows = sorted(
        [s.progress for s in _store.list_by_prefix(_STORE_PREFIX, limit=max(limit, 1))],
        key=lambda task: str(task.get("finished_at") or task.get("started_at") or task.get("created_at") or ""),
        reverse=True,
    )
    return rows[: max(limit, 1)]


async def get_objective_task_record(task_id: str) -> dict[str, Any]:
    state = _store.get(f"{_STORE_PREFIX}{task_id}")
    if state is not None:
        return state.progress
    return await _load_task_from_db(task_id)


def _render_task_csv(task: dict[str, Any]) -> str:
    if task["status"] != "completed":
        raise ValueError("任务尚未完成，暂时不能导出")
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["display_no", "question_type", "question", "options", "predicted_answer", "reason", "source_refs"])
    for row in task["results"]:
        options_text = " | ".join(f"{opt['label']}. {opt['text']}" for opt in row["options"])
        writer.writerow([
            row["display_no"], row["question_type"], row["question"], options_text,
            row["predicted_answer"], row["reason"], " | ".join(row["source_refs"]),
        ])
    return buf.getvalue()


async def export_objective_task_csv_async(task_id: str) -> str:
    task = await get_objective_task_record(task_id)
    return _render_task_csv(task)


def export_objective_task_csv(task_id: str) -> str:
    return _render_task_csv(get_objective_task(task_id))
