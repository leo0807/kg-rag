from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import desc, func, select

from ...db.models import AuditLog, User
from .harness_service import builtin_retrieval_cases_path


def _parse_sort_value(value: Any) -> tuple[int, str]:
    if isinstance(value, int):
        return (1, str(value).zfill(16))
    if isinstance(value, datetime):
        return (1, value.isoformat())
    return (1, str(value or ""))


def _normalize_runtime_item(source: str, task_type: str, task: dict[str, Any]) -> dict[str, Any]:
    total = int(task.get("total") or 0)
    completed = int(task.get("completed") or task.get("done") or 0)
    progress = round(completed / total, 4) if total > 0 else 0.0

    return {
        "source": source,
        "task_type": task_type,
        "task_id": task.get("task_id") or task.get("doc_id") or f"{source}:{task_type}",
        "label": task.get("filename") or task.get("doc_id") or task.get("current_doc") or task_type,
        "status": task.get("status") or "unknown",
        "progress": progress,
        "total": total,
        "completed": completed,
        "current": task.get("current_question") or task.get("current_doc") or task.get("step") or "",
        "message": task.get("message") or task.get("error") or "",
        "updated_at": task.get("finished_at") or task.get("started_at") or task.get("created_at") or "",
    }


def _load_runtime_sources() -> dict[str, list[dict[str, Any]]]:
    from ...main import list_ingest_tasks
    from ...routers.docs.reprocess import get_batch_task_snapshot, list_reprocess_tasks
    from ..evaluation.dataset_eval_service import list_dataset_eval_tasks
    from ..evaluation.objective_doc_eval_service import list_objective_eval_tasks
    from ..evaluation.retrieval_harness_service import list_retrieval_tasks

    batch_snapshot = get_batch_task_snapshot()
    sources = {
        "ingest": list_ingest_tasks(limit=20),
        "reprocess": list_reprocess_tasks(limit=20),
        "dataset_eval": list_dataset_eval_tasks(limit=20),
        "objective_eval": list_objective_eval_tasks(limit=20),
        "retrieval_eval": list_retrieval_tasks(limit=20),
        "batch_reprocess": [batch_snapshot] if batch_snapshot.get("status") not in {"", "idle"} else [],
    }
    return sources


def list_runtime_tasks(limit: int = 30) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source, tasks in _load_runtime_sources().items():
        if source == "batch_reprocess":
            rows.extend(_normalize_runtime_item(source, "batch_reprocess", task) for task in tasks)
            continue

        task_type = source
        rows.extend(_normalize_runtime_item(source, task_type, task) for task in tasks)

    rows.sort(key=lambda item: _parse_sort_value(item.get("updated_at")), reverse=True)
    return rows[: max(limit, 1)]


async def build_ops_overview(driver, db) -> dict[str, Any]:
    from ...routers.feedback import QueryFeedback

    with driver.session() as session:
        graph_stats = session.run(
            """
            MATCH (d:Document) WITH count(d) AS document_count
            MATCH (s:Section) WITH document_count, count(s) AS section_count
            OPTIONAL MATCH (i:Image)
            RETURN
                document_count,
                section_count,
                count(i) AS image_count,
                sum(CASE WHEN coalesce(i.is_drawing, false) THEN 1 ELSE 0 END) AS drawing_count
            """
        ).single()

    since_7d = datetime.utcnow() - timedelta(days=7)
    audit_count_res = await db.execute(
        select(func.count(AuditLog.id)).where(AuditLog.created_at >= since_7d)
    )
    negative_feedback_res = await db.execute(
        select(func.count(QueryFeedback.id)).where(
            QueryFeedback.created_at >= since_7d,
            QueryFeedback.rating == -1,
        )
    )
    audit_rows = await db.execute(
        select(AuditLog, User.username)
        .join(User, AuditLog.user_id == User.id)
        .order_by(desc(AuditLog.created_at))
        .limit(10)
    )
    runtime_tasks = list_runtime_tasks(limit=50)
    status_counts: dict[str, int] = {}
    for item in runtime_tasks:
        status = item.get("status") or "unknown"
        status_counts[status] = status_counts.get(status, 0) + 1

    sample_path = builtin_retrieval_cases_path()
    sample_count = 0
    if sample_path.exists():
        sample_count = sum(1 for line in sample_path.read_text(encoding="utf-8").splitlines() if line.strip())

    return {
        "knowledge": {
            "documents": int(graph_stats["document_count"] or 0),
            "sections": int(graph_stats["section_count"] or 0),
            "images": int(graph_stats["image_count"] or 0),
            "drawings": int(graph_stats["drawing_count"] or 0),
        },
        "quality": {
            "retrieval_cases": sample_count,
            "negative_feedback_7d": int(negative_feedback_res.scalar() or 0),
            "audit_events_7d": int(audit_count_res.scalar() or 0),
        },
        "runtime": {
            "total": len(runtime_tasks),
            "running": status_counts.get("running", 0),
            "failed": status_counts.get("failed", 0),
            "queued": status_counts.get("queued", 0),
            "completed": status_counts.get("completed", 0),
        },
        "recent_audits": [
            {
                "id": log.id,
                "action": log.action,
                "resource": log.resource,
                "detail": log.detail,
                "username": username,
                "created_at": log.created_at.isoformat(),
            }
            for log, username in audit_rows.all()
        ],
    }
