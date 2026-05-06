"""
Per-document task state tracking for the processing dashboard.
State is stored in Redis under processing:task:{task_id} keys.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from ..infra.cache import get_redis

STAGES_ORDER = ["解析章节", "向量化", "写入Neo4j", "ES索引"]

K_PROC_ERRORS          = "processing:errors"
K_PROC_COMPLETED_TODAY = "processing:stats:completed_today"
K_PROC_FAILED_TODAY    = "processing:stats:failed_today"
K_PROC_ACTIVE_TASKS    = "processing:active_tasks"


def _r():
    return get_redis()


def task_key(task_id: str) -> str:
    return f"processing:task:{task_id}"


def task_create(task_id: str, doc_id: str, file_path: str) -> None:
    r = _r()
    payload = {
        "task_id": task_id,
        "doc_id": doc_id,
        "file_path": file_path,
        "stage": "解析章节",
        "progress": 5,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "stages_completed": [],
        "stages_pending": list(STAGES_ORDER),
        "status": "running",
    }
    r.set(task_key(task_id), json.dumps(payload), ex=86400)
    r.sadd(K_PROC_ACTIVE_TASKS, task_id)


def task_update_stage(task_id: str, stage: str, progress: int) -> None:
    r = _r()
    raw = r.get(task_key(task_id))
    if not raw:
        return
    task = json.loads(raw)
    idx = STAGES_ORDER.index(stage) if stage in STAGES_ORDER else -1
    task.update({
        "stage": stage,
        "progress": progress,
        "stages_completed": STAGES_ORDER[:idx] if idx >= 0 else task.get("stages_completed", []),
        "stages_pending": STAGES_ORDER[idx + 1:] if idx >= 0 else task.get("stages_pending", []),
    })
    r.set(task_key(task_id), json.dumps(task), ex=86400)


def task_complete(task_id: str) -> None:
    r = _r()
    raw = r.get(task_key(task_id))
    if raw:
        task = json.loads(raw)
        task.update({"status": "completed", "progress": 100, "stage": "完成",
                     "stages_completed": list(STAGES_ORDER), "stages_pending": []})
        r.set(task_key(task_id), json.dumps(task), ex=86400)
    r.srem(K_PROC_ACTIVE_TASKS, task_id)
    r.incr(K_PROC_COMPLETED_TODAY)


def task_fail(task_id: str, doc_id: str, stage: str, error: str, file_path: str = "") -> None:
    r = _r()
    raw = r.get(task_key(task_id))
    if raw:
        task = json.loads(raw)
        task.update({"status": "failed", "stage": f"失败: {stage}"})
        r.set(task_key(task_id), json.dumps(task), ex=86400)
    r.srem(K_PROC_ACTIVE_TASKS, task_id)
    entry = json.dumps({
        "task_id": task_id, "doc_id": doc_id, "stage": stage,
        "error": str(error)[:300],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "file_path": file_path,
    })
    r.lpush(K_PROC_ERRORS, entry)
    r.ltrim(K_PROC_ERRORS, 0, 49)
    r.incr(K_PROC_FAILED_TODAY)


def get_processing_status(batch_total: int, batch_done: int, batch_failed: int) -> dict[str, Any]:
    r = _r()
    active_ids = r.smembers(K_PROC_ACTIVE_TASKS) or set()
    active_tasks = []
    for tid in active_ids:
        raw = r.get(task_key(tid))
        if not raw:
            continue
        task = json.loads(raw)
        if task.get("status") == "running":
            try:
                start_dt = datetime.fromisoformat(task["started_at"].replace("Z", "+00:00"))
                task["elapsed_seconds"] = int((datetime.now(timezone.utc) - start_dt).total_seconds())
            except Exception:
                task["elapsed_seconds"] = 0
            active_tasks.append(task)

    queue_size = max(0, batch_total - batch_done - batch_failed - len(active_tasks))

    errors_raw = r.lrange(K_PROC_ERRORS, 0, 9)
    recent_errors = []
    for raw_e in errors_raw:
        try:
            err = json.loads(raw_e)
            ts = err.get("timestamp", "")
            if ts:
                try:
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    err["timestamp"] = dt.strftime("%H:%M")
                except Exception:
                    pass
            recent_errors.append(err)
        except Exception:
            pass

    return {
        "active_tasks":    active_tasks,
        "queue_size":      queue_size,
        "completed_today": int(r.get(K_PROC_COMPLETED_TODAY) or 0),
        "failed_today":    int(r.get(K_PROC_FAILED_TODAY)    or 0),
        "recent_errors":   recent_errors,
    }


def clear_stats() -> None:
    r = _r()
    r.delete(K_PROC_COMPLETED_TODAY, K_PROC_FAILED_TODAY, K_PROC_ERRORS)
