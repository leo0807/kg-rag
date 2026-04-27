from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import desc, func, select

from ...db.models import AuditLog, User
from ..infra.health import health_monitor
from .harness_service import builtin_retrieval_cases_path
from .presence_service import get_presence_snapshot


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
    from ...routers.docs.ingest import list_ingest_tasks
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


def summarize_system_pressure(
    *,
    services: dict[str, dict[str, Any]],
    runtime: dict[str, int],
    active_users: int,
    requests_1m: int,
) -> dict[str, Any]:
    score = 0
    factors: list[str] = []

    down_services = [name for name, info in services.items() if info.get("state") == "down"]
    if down_services:
        score += 55
        factors.append(f"依赖异常: {', '.join(down_services)}")

    peak_latency = max((float(info.get("latency_ms") or 0) for info in services.values()), default=0.0)
    if peak_latency >= 1200:
        score += 18
        factors.append(f"后端探活延迟偏高 ({int(peak_latency)}ms)")
    elif peak_latency >= 400:
        score += 8
        factors.append(f"后端延迟抬升 ({int(peak_latency)}ms)")

    running = int(runtime.get("running") or 0)
    queued = int(runtime.get("queued") or 0)
    failed = int(runtime.get("failed") or 0)

    if running >= 6:
        score += 18
        factors.append(f"运行中任务较多 ({running})")
    elif running >= 3:
        score += 8
        factors.append(f"运行中任务上升 ({running})")

    if queued >= 6:
        score += 18
        factors.append(f"排队任务较多 ({queued})")
    elif queued >= 2:
        score += 8
        factors.append(f"存在排队任务 ({queued})")

    if failed > 0:
        score += min(12 + failed * 2, 20)
        factors.append(f"近期存在失败任务 ({failed})")

    if active_users >= 12:
        score += 14
        factors.append(f"在线人数较高 ({active_users})")
    elif active_users >= 5:
        score += 6
        factors.append(f"在线人数增长 ({active_users})")

    if requests_1m >= 240:
        score += 16
        factors.append(f"近 1 分钟请求量高 ({requests_1m})")
    elif requests_1m >= 90:
        score += 8
        factors.append(f"近 1 分钟请求活跃 ({requests_1m})")

    if score >= 55:
        level = "high"
        summary = "系统正处于高压或降级状态"
    elif score >= 24:
        level = "medium"
        summary = "系统负载上升，建议关注排队与延迟"
    else:
        level = "low"
        summary = "系统运行平稳"

    if not factors:
        factors.append("核心依赖和任务队列均稳定")

    return {
        "level": level,
        "score": min(score, 100),
        "summary": summary,
        "factors": factors[:4],
    }


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
    runtime = {
        "total": len(runtime_tasks),
        "running": status_counts.get("running", 0),
        "failed": status_counts.get("failed", 0),
        "queued": status_counts.get("queued", 0),
        "completed": status_counts.get("completed", 0),
    }
    services = health_monitor.to_dict()
    presence = await get_presence_snapshot(db)
    pressure = summarize_system_pressure(
        services=services,
        runtime=runtime,
        active_users=int(presence["active_users"] or 0),
        requests_1m=int(presence["requests_1m"] or 0),
    )

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
        "runtime": runtime,
        "services": services,
        "presence": presence,
        "pressure": pressure,
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
