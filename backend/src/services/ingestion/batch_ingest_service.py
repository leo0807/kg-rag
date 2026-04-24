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
import time
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List

from ..parsing.parser import parse
from ..graph.neo4j_writer import write_document
from ..infra.cache import get_redis
from ...core.database import get_driver

logger = logging.getLogger(__name__)

# --- Redis Keys ---
K_BATCH_STATUS    = "batch_ingest:status"    # idle, running, paused, stopping
K_BATCH_TOTAL     = "batch_ingest:total"
K_BATCH_DONE      = "batch_ingest:done"
K_BATCH_FAILED    = "batch_ingest:failed"
K_BATCH_CURRENT   = "batch_ingest:current"
K_BATCH_PAUSE     = "batch_ingest:pause"
K_BATCH_STOP      = "batch_ingest:stop"
K_BATCH_LOGS      = "batch_ingest:logs"      # List for real-time audit

_ALL_KEYS = (K_BATCH_STATUS, K_BATCH_TOTAL, K_BATCH_DONE, K_BATCH_FAILED, 
             K_BATCH_CURRENT, K_BATCH_PAUSE, K_BATCH_STOP, K_BATCH_LOGS)

_task: Optional[asyncio.Task] = None

def _redis():
    return get_redis()

def _add_log(msg: str, level: str = "INFO"):
    r = _redis()
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_entry = json.dumps({"time": timestamp, "level": level, "msg": msg})
    r.lpush(K_BATCH_LOGS, log_entry)
    r.ltrim(K_BATCH_LOGS, 0, 99) # Keep last 100 logs
    if level == "ERROR":
        logger.error(f"[BatchIngest] {msg}")
    else:
        logger.info(f"[BatchIngest] {msg}")

async def _ingest_loop(file_paths: List[Path]):
    r = _redis()
    driver = get_driver()
    
    total = len(file_paths)
    r.set(K_BATCH_TOTAL, total)
    r.set(K_BATCH_DONE, 0)
    r.set(K_BATCH_FAILED, 0)
    
    _add_log(f"开始批量处理 {total} 个文件")

    for path in file_paths:
        # Check Stop
        if r.exists(K_BATCH_STOP):
            _add_log("收到停止信号，终止任务", "WARNING")
            break

        # Check Pause
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

        try:
            # 1. 解析
            doc = await asyncio.to_thread(parse, path)
            # 2. 写入数据库 (Neo4j, Milvus, ES)
            await asyncio.to_thread(write_document, doc)
            
            r.incr(K_BATCH_DONE)
            _add_log(f"成功入库: {doc.doc_id} ({len(doc.sections)} 章节)", "SUCCESS")
        except Exception as e:
            r.incr(K_BATCH_FAILED)
            _add_log(f"处理失败 {path.name}: {str(e)}", "ERROR")

        # 稍微喘息一下
        await asyncio.sleep(1)

    # Cleanup
    status = "completed" if not r.exists(K_BATCH_STOP) else "stopped"
    r.set(K_BATCH_STATUS, status)
    r.delete(K_BATCH_STOP, K_BATCH_PAUSE)
    r.set(K_BATCH_CURRENT, "")
    _add_log(f"任务结束 状态: {status}")

async def start_batch_ingest(directory: str) -> dict:
    global _task
    r = _redis()
    
    if _task and not _task.done():
        return {"ok": False, "reason": "已有任务在运行"}

    path = Path(directory)
    if not path.exists() or not path.is_dir():
        return {"ok": False, "reason": "目录不存在"}

    files = sorted(list(path.glob("*.pdf")) + list(path.glob("*.docx")) + list(path.glob("*.doc")))
    if not files:
        return {"ok": False, "reason": "目录下未找到支持的文档 (*.pdf, *.docx, *.doc)"}

    # Reset state
    r.delete(*_ALL_KEYS)
    r.set(K_BATCH_STATUS, "running")
    
    _task = asyncio.create_task(_ingest_loop(files))
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
        "status": r.get(K_BATCH_STATUS) or "idle",
        "total": int(r.get(K_BATCH_TOTAL) or 0),
        "done": int(r.get(K_BATCH_DONE) or 0),
        "failed": int(r.get(K_BATCH_FAILED) or 0),
        "current": r.get(K_BATCH_CURRENT) or "",
        "logs": logs
    }
