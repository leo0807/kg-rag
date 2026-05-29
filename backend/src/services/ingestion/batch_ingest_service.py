"""
src/services/batch_ingest_service.py
批量文档入库服务

支持扫描指定目录下的 PDF 文件并批量处理。
提供暂停、恢复、停止及实时日志功能。
状态持久化到 Redis。
"""
from __future__ import annotations

import asyncio
import logging
import time as _time
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from ..parsing.parser import parse
from ..graph.neo4j_writer import write_document
from ..infra.cache import get_redis
from ..alert_service import alert_service
from .processing_tracker import (
    task_create, task_update_stage, task_complete, task_fail,
    get_processing_status as _get_proc_status, clear_stats,
    task_key,
)

logger = logging.getLogger(__name__)

# --- Redis Keys ---
K_BATCH_STATUS  = "batch_ingest:status"
K_BATCH_TOTAL   = "batch_ingest:total"
K_BATCH_DONE    = "batch_ingest:done"
K_BATCH_FAILED  = "batch_ingest:failed"
K_BATCH_CURRENT = "batch_ingest:current"
K_BATCH_PAUSE   = "batch_ingest:pause"
K_BATCH_STOP    = "batch_ingest:stop"
K_BATCH_LOGS    = "batch_ingest:logs"

_ALL_KEYS = (K_BATCH_STATUS, K_BATCH_TOTAL, K_BATCH_DONE, K_BATCH_FAILED,
             K_BATCH_CURRENT, K_BATCH_PAUSE, K_BATCH_STOP, K_BATCH_LOGS)

def _redis():
    return get_redis()


def _add_log(msg: str, level: str = "INFO"):
    r = _redis()
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_entry = json.dumps({"time": timestamp, "level": level, "msg": msg})
    r.lpush(K_BATCH_LOGS, log_entry)
    r.ltrim(K_BATCH_LOGS, 0, 99)
    if level == "ERROR":
        logger.error("[BatchIngest] %s", msg)
    else:
        logger.info("[BatchIngest] %s", msg)


async def _ingest_loop(file_paths: List[Path], driver=None):
    r = _redis()
    total = len(file_paths)
    r.set(K_BATCH_TOTAL, total)
    r.set(K_BATCH_DONE, 0)
    r.set(K_BATCH_FAILED, 0)
    _add_log(f"开始批量处理 {total} 个文件")

    for path in file_paths:
        if r.exists(K_BATCH_STOP):
            _add_log("收到停止信号，终止任务", "WARNING")
            break

        while r.exists(K_BATCH_PAUSE):
            if r.exists(K_BATCH_STOP):
                break
            r.set(K_BATCH_STATUS, "paused")
            await asyncio.sleep(2)

        if r.exists(K_BATCH_STOP):
            break

        r.set(K_BATCH_STATUS, "running")
        r.set(K_BATCH_CURRENT, path.name)
        _add_log(f"正在处理: {path.name}")

        doc_id  = path.stem
        tid     = f"ingest_{doc_id}_{int(_time.time())}"
        task_create(tid, doc_id, str(path))
        current_stage: list[str | None] = [None]

        def _on_stage(stage: str, pct: int) -> None:
            current_stage[0] = stage
            task_update_stage(tid, stage, pct)

        try:
            task_update_stage(tid, "解析章节", 10)
            doc = await asyncio.to_thread(parse, path)
            await asyncio.to_thread(write_document, doc, _on_stage, driver=driver)
            task_complete(tid)
            r.incr(K_BATCH_DONE)
            _add_log(f"成功入库: {doc.doc_id} ({len(doc.sections)} 章节)", "SUCCESS")
        except Exception as e:
            failed_stage = current_stage[0] or "解析章节"
            task_fail(tid, doc_id, failed_stage, str(e), str(path))
            r.incr(K_BATCH_FAILED)
            _add_log(f"处理失败 {path.name}: {e}", "ERROR")

        await asyncio.sleep(1)

    status = "completed" if not r.exists(K_BATCH_STOP) else "stopped"
    r.set(K_BATCH_STATUS, status)
    r.delete(K_BATCH_STOP, K_BATCH_PAUSE)
    r.set(K_BATCH_CURRENT, "")
    _add_log(f"任务结束 状态: {status}")

    # 批量失败告警：失败数 > 5
    fail_count = int(r.get(K_BATCH_FAILED) or 0)
    if fail_count > 5:
        await alert_service.send_alert(
            "文档解析批量失败",
            f"本次批量处理已有 **{fail_count}** 份文档解析失败\n"
            f"共处理：{total} 份，成功：{total - fail_count} 份",
            level="error",
        )


async def start_batch_ingest(directory: str) -> dict:
    from ...tasks.ingestion_tasks import run_batch_ingest

    r = _redis()
    if r.get(K_BATCH_STATUS) in (b"running", b"paused", "running", "paused"):
        return {"ok": False, "reason": "已有任务在运行"}

    path = Path(directory)
    if not path.exists() or not path.is_dir():
        return {"ok": False, "reason": "目录不存在"}

    files = sorted(
        list(path.glob("*.pdf")) + list(path.glob("*.docx")) + list(path.glob("*.doc"))
    )
    if not files:
        return {"ok": False, "reason": "目录下未找到支持的文档 (*.pdf, *.docx, *.doc)"}

    r.delete(*_ALL_KEYS)
    r.set(K_BATCH_STATUS, "running")
    run_batch_ingest.delay([str(f) for f in files])
    return {"ok": True, "total": len(files)}


def pause_batch():
    r = _redis()
    r.set(K_BATCH_PAUSE, "1")
    r.set(K_BATCH_STATUS, "paused")
    return {"ok": True}


def resume_batch():
    r = _redis()
    r.delete(K_BATCH_PAUSE)
    r.set(K_BATCH_STATUS, "running")
    return {"ok": True}


def stop_batch():
    r = _redis()
    r.set(K_BATCH_STOP, "1")
    r.set(K_BATCH_STATUS, "stopping")
    return {"ok": True}


def get_batch_status():
    r = _redis()
    logs_raw = r.lrange(K_BATCH_LOGS, 0, -1)
    logs = [json.loads(l) for l in logs_raw]
    return {
        "status":  r.get(K_BATCH_STATUS) or "idle",
        "total":   int(r.get(K_BATCH_TOTAL)  or 0),
        "done":    int(r.get(K_BATCH_DONE)   or 0),
        "failed":  int(r.get(K_BATCH_FAILED) or 0),
        "current": r.get(K_BATCH_CURRENT) or "",
        "logs":    logs,
    }


def get_processing_status() -> dict:
    r = _redis()
    return _get_proc_status(
        batch_total  = int(r.get(K_BATCH_TOTAL)  or 0),
        batch_done   = int(r.get(K_BATCH_DONE)   or 0),
        batch_failed = int(r.get(K_BATCH_FAILED) or 0),
    )


async def retry_task(task_id: str) -> dict:
    r = _redis()
    import json as _json
    raw = r.get(task_key(task_id))
    if not raw:
        return {"ok": False, "reason": "任务不存在"}
    info = _json.loads(raw)
    file_path = info.get("file_path", "")
    if not file_path:
        return {"ok": False, "reason": "任务无文件路径信息"}
    path = Path(file_path)
    if not path.exists():
        return {"ok": False, "reason": f"文件不存在: {file_path}"}

    doc_id  = info.get("doc_id", path.stem)
    new_tid = f"retry_{doc_id}_{int(_time.time())}"
    task_create(new_tid, doc_id, str(path))
    _add_log(f"重试任务: {path.name}")

    async def _retry():
        current: list[str | None] = [None]

        def _on_stage(stage: str, pct: int) -> None:
            current[0] = stage
            task_update_stage(new_tid, stage, pct)

        try:
            task_update_stage(new_tid, "解析章节", 10)
            doc = await asyncio.to_thread(parse, path)
            await asyncio.to_thread(write_document, doc, _on_stage)
            task_complete(new_tid)
            _add_log(f"重试成功: {path.name}", "SUCCESS")
        except Exception as exc:
            task_fail(new_tid, doc_id, current[0] or "解析章节", str(exc), str(path))
            _add_log(f"重试失败 {path.name}: {exc}", "ERROR")

    asyncio.create_task(_retry())
    return {"ok": True, "new_task_id": new_tid}


def clear_completed_tasks() -> dict:
    clear_stats()
    return {"ok": True}
