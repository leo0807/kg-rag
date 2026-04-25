from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from .backfill_helpers import (
    K_CURRENT,
    K_DONE,
    K_PAUSE,
    K_STARTED_AT,
    K_STATUS,
    K_STOP,
    K_TOTAL,
    _ALL_KEYS,
    _count_all_docs,
    _extract_images_for_doc,
    _find_pdf,
    _get_pending_docs,
    _redis,
)

logger = logging.getLogger(__name__)

_task: Optional[asyncio.Task] = None


async def _backfill_loop(doc_ids: list[str]) -> None:
    from ...core.database import get_driver
    from .reprocess_service import load_sections

    redis_client = _redis()
    driver = get_driver()
    stopped = False

    for doc_id in doc_ids:
        if redis_client.exists(K_STOP):
            stopped = True
            break

        while redis_client.exists(K_PAUSE):
            if redis_client.exists(K_STOP):
                stopped = True
                break
            redis_client.set(K_STATUS, "paused")
            await asyncio.sleep(2)

        if stopped:
            break

        redis_client.set(K_STATUS, "running")
        redis_client.set(K_CURRENT, doc_id)
        logger.info("[backfill] 处理 doc_id=%s", doc_id)

        try:
            pdf_path = await asyncio.to_thread(_find_pdf, doc_id)
            if not pdf_path:
                logger.warning("[backfill] 未找到 PDF，跳过 doc_id=%s", doc_id)
            else:
                sections = await asyncio.to_thread(load_sections, driver, doc_id)
                await asyncio.to_thread(_extract_images_for_doc, doc_id, pdf_path, sections, driver)
        except Exception as e:
            logger.warning("[backfill] 文档处理失败 doc_id=%s: %s", doc_id, e)

        redis_client.incr(K_DONE)
        await asyncio.sleep(5)

    if stopped:
        redis_client.delete(*_ALL_KEYS)
        redis_client.set(K_STATUS, "idle")
        logger.info("[backfill] 任务已手动停止，所有进度数据已清除")
    else:
        redis_client.set(K_STATUS, "completed")
        redis_client.set(K_CURRENT, "")
        total = int(redis_client.get(K_TOTAL) or 0)
        logger.info("[backfill] 全部完成，共 %d 份文档", total)


async def start_backfill(done_offset: int = 0) -> dict:
    global _task
    from ...core.database import get_driver

    redis_client = _redis()
    if _task and not _task.done():
        return {"status": "already_running"}

    driver = get_driver()
    total = await asyncio.to_thread(_count_all_docs, driver)
    pending = await asyncio.to_thread(_get_pending_docs, driver)

    if not pending:
        redis_client.set(K_STATUS, "completed")
        redis_client.set(K_DONE, total)
        redis_client.set(K_TOTAL, total)
        return {"status": "nothing_to_do", "total": total}

    redis_client.set(K_STARTED_AT, datetime.now(timezone.utc).isoformat())
    redis_client.set(K_TOTAL, total)
    redis_client.set(K_DONE, done_offset)
    redis_client.set(K_STATUS, "running")
    redis_client.delete(K_PAUSE)

    _task = asyncio.create_task(_backfill_loop(pending))
    logger.info("[backfill] 任务启动 total=%d pending=%d", total, len(pending))
    return {"status": "started", "total": total, "pending": len(pending)}


def pause_backfill() -> dict:
    redis_client = _redis()
    if redis_client.get(K_STATUS) not in ("running",):
        return {"ok": False, "reason": "任务未在运行"}
    redis_client.set(K_PAUSE, "1")
    return {"ok": True, "message": "暂停信号已发送"}


def resume_backfill() -> dict:
    redis_client = _redis()
    redis_client.delete(K_PAUSE)
    redis_client.set(K_STATUS, "running")
    return {"ok": True, "message": "已恢复"}


def stop_backfill() -> dict:
    global _task
    redis_client = _redis()
    status = redis_client.get(K_STATUS)
    if status not in ("running", "paused"):
        return {"ok": False, "reason": "任务未在运行中"}
    redis_client.set(K_STOP, "1")
    if _task and not _task.done():
        _task.cancel()
    return {"ok": True, "message": "停止信号已发送，任务将在当前文档处理完后停止"}


def get_backfill_status() -> dict:
    redis_client = _redis()
    status = redis_client.get(K_STATUS) or "idle"
    total = int(redis_client.get(K_TOTAL) or 0)
    done = int(redis_client.get(K_DONE) or 0)
    current = redis_client.get(K_CURRENT) or ""
    started_at = redis_client.get(K_STARTED_AT) or ""

    elapsed = 0
    estimated = 0
    if started_at:
        try:
            dt = datetime.fromisoformat(started_at)
            elapsed = int((datetime.now(timezone.utc) - dt).total_seconds())
            if done > 0 and elapsed > 0:
                rate = done / elapsed
                estimated = int((total - done) / rate) if rate > 0 else 0
        except Exception:
            pass

    return {
        "status": status,
        "total": total,
        "done": done,
        "current_doc": current,
        "percent": round(done / total * 100, 1) if total > 0 else 0.0,
        "elapsed_seconds": elapsed,
        "estimated_remaining_seconds": estimated,
    }


async def try_resume_on_startup() -> None:
    redis_client = _redis()
    status = redis_client.get(K_STATUS)

    if status in ("running", "paused"):
        done = int(redis_client.get(K_DONE) or 0)
        total = int(redis_client.get(K_TOTAL) or 0)
        if total == 0:
            return
        logger.info(
            "[backfill] 检测到未完成任务 (done=%d/%d status=%s)，服务重启后自动续跑",
            done,
            total,
            status,
        )
        redis_client.delete(K_PAUSE)
        try:
            await start_backfill(done_offset=done)
        except Exception as e:
            logger.warning("[backfill] 自动续跑失败: %s", e)
    elif status is None:
        try:
            from ...core.database import get_driver

            driver = get_driver()
            pending = await asyncio.to_thread(_get_pending_docs, driver)
            if pending:
                logger.info(
                    "[backfill] Redis无状态，Neo4j中有 %d 份文档仍缺少图片，自动续跑",
                    len(pending),
                )
                await start_backfill(done_offset=0)
            else:
                logger.debug("[backfill] Redis无状态，Neo4j无待处理文档，跳过续跑")
        except Exception as e:
            logger.warning("[backfill] 兜底检查失败，跳过续跑: %s", e)
