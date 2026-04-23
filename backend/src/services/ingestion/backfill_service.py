"""
src/services/backfill_service.py
后台图片补全服务

扫描 Neo4j 中所有没有 :Image 子节点的 :Document，
从 PDF 提取图片 → 上传 MinIO → 写入 Neo4j，
支持暂停/恢复，进度写入 Redis。
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Redis key 常量 ────────────────────────────────────────────────────────────
K_TOTAL      = "backfill:total"
K_DONE       = "backfill:done"
K_CURRENT    = "backfill:current"
K_STATUS     = "backfill:status"
K_STARTED_AT = "backfill:started_at"
K_PAUSE      = "backfill:pause"
K_STOP       = "backfill:stop"

_ALL_KEYS = (K_TOTAL, K_DONE, K_CURRENT, K_STATUS, K_STARTED_AT, K_PAUSE, K_STOP)

# ── 全局任务句柄 ───────────────────────────────────────────────────────────────
_task: Optional[asyncio.Task] = None


# ── 内部工具 ──────────────────────────────────────────────────────────────────

def _redis():
    from ..cache import get_redis
    return get_redis()


def _get_pending_docs(driver) -> list[str]:
    """查询所有没有 :Image 子节点的 Document（按 doc_id 升序）。"""
    with driver.session() as session:
        result = session.run("""
            MATCH (d:Document)
            WHERE d.title IS NOT NULL
              AND NOT (d)-[:HAS_IMAGE]->(:Image)
            RETURN d.name AS doc_id
            ORDER BY d.name ASC
        """)
        return [r["doc_id"] for r in result]


def _count_all_docs(driver) -> int:
    """返回库中有 title 的 Document 总数。"""
    with driver.session() as session:
        row = session.run(
            "MATCH (d:Document) WHERE d.title IS NOT NULL RETURN count(d) AS n"
        ).single()
        return row["n"] if row else 0


def _find_pdf(doc_id: str) -> Optional[Path]:
    """在 uploads/docs/ 和 uploads/ 中查找对应 PDF 文件。"""
    for base in (Path("uploads/docs"), Path("uploads")):
        for ext in ("pdf", "PDF"):
            matches = sorted(base.glob(f"{doc_id}*.{ext}"))
            if matches:
                return matches[0]
    return None


def _delete_existing_images_for_doc(doc_id: str, driver) -> int:
    """
    删除文档下已有图片节点及其关系。
    用于重新抽图时替换历史结果，避免旧的重复图片残留。
    """
    with driver.session() as session:
        row = session.run("""
            MATCH (d:Document {name: $doc_id})-[:HAS_IMAGE]->(i:Image)
            WITH collect(DISTINCT i) AS images
            RETURN size(images) AS count
        """, doc_id=doc_id).single()
        count = int(row["count"]) if row and row["count"] is not None else 0
        if count:
            session.run("""
                MATCH (d:Document {name: $doc_id})-[:HAS_IMAGE]->(i:Image)
                WITH collect(DISTINCT i) AS images
                UNWIND images AS image
                DETACH DELETE image
            """, doc_id=doc_id)
    return count


def _extract_images_for_doc(doc_id: str, pdf_path: Path, sections: list, driver) -> int:
    """
    从单份 PDF 提取图片，写入本地 + MinIO + Neo4j。
    返回成功写入的图片数，失败时抛出异常交由调用方处理。
    """
    from ..pdf_image_extractor import extract_images_from_pdf

    # 页码 → chunk_id（取页面上最后一个 section）
    page_to_chunk: dict[int, str] = {}
    for s in sections:
        if isinstance(s, dict):
            pidx = s.get("page_idx")
            cid  = s.get("chunk_id")
        else:
            pidx = getattr(s, "page_idx", None)
            cid  = getattr(s, "chunk_id", None)
        if pidx is not None and cid:
            page_to_chunk[pidx] = cid

    sorted_pages = sorted(page_to_chunk.keys())

    def _find_chunk(page_num: int) -> Optional[str]:
        best = None
        for p in sorted_pages:
            if p <= page_num:
                best = page_to_chunk[p]
            else:
                break
        return best

    extracted_images = extract_images_from_pdf(str(pdf_path), doc_id)
    image_nodes = [
        {
            "image_id": img.image_id,
            "doc_id": doc_id,
            "page_num": img.page,
            "path": img.path,
            "minio_path": img.minio_key,
            "content_hash": img.content_hash,
            "is_drawing": False,
            "chunk_id": _find_chunk(max(int(img.page) - 1, 0)),
        }
        for img in extracted_images
    ]

    if not image_nodes:
        return 0

    with driver.session() as session:
        session.run("""
            UNWIND $images AS img
            MATCH (d:Document {name: img.doc_id})
            MERGE (i:Image {image_id: img.image_id})
            SET i.doc_id     = img.doc_id,
                i.page       = img.page_num,
                i.page_num   = img.page_num,
                i.path       = img.path,
                i.minio_path = img.minio_path,
                i.content_hash = img.content_hash,
                i.is_drawing = img.is_drawing
            MERGE (d)-[:HAS_IMAGE]->(i)
        """, images=image_nodes)

        section_links = [n for n in image_nodes if n.get("chunk_id")]
        if section_links:
            session.run("""
                UNWIND $links AS lnk
                MATCH (s:Section {chunk_id: lnk.chunk_id})
                MATCH (i:Image   {image_id: lnk.image_id})
                MERGE (s)-[:HAS_IMAGE]->(i)
            """, links=section_links)

    logger.info(
        "[backfill] 图片写入完成 doc_id=%s count=%d",
        doc_id,
        len(image_nodes),
    )
    return len(image_nodes)


def extract_images_for_doc(doc_id: str, pdf_path: Path, sections: list, driver) -> int:
    """公开封装：提取 PDF 图片并写入图谱。"""
    return _extract_images_for_doc(doc_id, pdf_path, sections, driver)


# ── 异步后台主循环 ─────────────────────────────────────────────────────────────

async def _backfill_loop(doc_ids: list[str]) -> None:
    """逐文档处理，支持 Redis pause key 暂停，单文档失败后继续。"""
    from ...core.database import get_driver
    from .reprocess_service import load_sections

    r      = _redis()
    driver = get_driver()

    stopped = False

    for doc_id in doc_ids:
        # ── 停止检查 ─────────────────────────────────────────────────────────
        if r.exists(K_STOP):
            stopped = True
            break

        # ── 暂停检查：循环等待直到 backfill:pause key 被删除 ────────────────
        while r.exists(K_PAUSE):
            if r.exists(K_STOP):
                stopped = True
                break
            r.set(K_STATUS, "paused")
            await asyncio.sleep(2)

        if stopped:
            break

        r.set(K_STATUS, "running")
        r.set(K_CURRENT, doc_id)
        logger.info("[backfill] 处理 doc_id=%s", doc_id)

        try:
            pdf_path = await asyncio.to_thread(_find_pdf, doc_id)
            if not pdf_path:
                logger.warning("[backfill] 未找到 PDF，跳过 doc_id=%s", doc_id)
            else:
                sections = await asyncio.to_thread(load_sections, driver, doc_id)
                await asyncio.to_thread(
                    _extract_images_for_doc, doc_id, pdf_path, sections, driver
                )
        except Exception as e:
            logger.warning("[backfill] 文档处理失败 doc_id=%s: %s", doc_id, e)

        r.incr(K_DONE)

        # 每份文档间隔 5 秒，避免压满服务器
        await asyncio.sleep(5)

    if stopped:
        # 停止：清除所有进度数据，状态归 idle
        r.delete(*_ALL_KEYS)
        r.set(K_STATUS, "idle")
        logger.info("[backfill] 任务已手动停止，所有进度数据已清除")
    else:
        r.set(K_STATUS, "completed")
        r.set(K_CURRENT, "")
        total = int(r.get(K_TOTAL) or 0)
        logger.info("[backfill] 全部完成，共 %d 份文档", total)


# ── 公开接口 ──────────────────────────────────────────────────────────────────

async def start_backfill(done_offset: int = 0) -> dict:
    """
    启动（或续跑）补全任务。

    done_offset: 已完成文档数（续跑时传入，使进度显示连续）。
    """
    global _task
    from ...core.database import get_driver

    r = _redis()

    # 已有任务在运行，直接返回
    if _task and not _task.done():
        return {"status": "already_running"}

    driver  = get_driver()
    total   = await asyncio.to_thread(_count_all_docs, driver)
    pending = await asyncio.to_thread(_get_pending_docs, driver)

    if not pending:
        r.set(K_STATUS, "completed")
        r.set(K_DONE,   total)
        r.set(K_TOTAL,  total)
        return {"status": "nothing_to_do", "total": total}

    r.set(K_STARTED_AT, datetime.now(timezone.utc).isoformat())
    r.set(K_TOTAL,      total)
    r.set(K_DONE,       done_offset)
    r.set(K_STATUS,     "running")
    r.delete(K_PAUSE)

    _task = asyncio.create_task(_backfill_loop(pending))
    logger.info("[backfill] 任务启动 total=%d pending=%d", total, len(pending))
    return {"status": "started", "total": total, "pending": len(pending)}


def pause_backfill() -> dict:
    """设置 backfill:pause key，循环在下次检查时进入等待。"""
    r = _redis()
    if r.get(K_STATUS) not in ("running",):
        return {"ok": False, "reason": "任务未在运行"}
    r.set(K_PAUSE, "1")
    return {"ok": True, "message": "暂停信号已发送"}


def resume_backfill() -> dict:
    """删除 backfill:pause key，恢复运行。"""
    r = _redis()
    r.delete(K_PAUSE)
    r.set(K_STATUS, "running")
    return {"ok": True, "message": "已恢复"}


def stop_backfill() -> dict:
    """
    停止任务并清除所有进度数据，服务重启后任务不会自动恢复。

    方式：设置 backfill:stop key → 后台循环在下次文档间隙检测到后退出并清除所有 key。
    若 asyncio Task 仍在处理当前文档，会在该文档完成后停止（不打断正在进行的 I/O）。
    """
    global _task
    r = _redis()
    status = r.get(K_STATUS)
    if status not in ("running", "paused"):
        return {"ok": False, "reason": "任务未在运行中"}
    r.set(K_STOP, "1")
    # 同时取消异步任务（若仍在等待 asyncio.sleep）
    if _task and not _task.done():
        _task.cancel()
    return {"ok": True, "message": "停止信号已发送，任务将在当前文档处理完后停止"}


def get_backfill_status() -> dict:
    """读取 Redis 进度，返回完整状态字典。"""
    r = _redis()
    status     = r.get(K_STATUS)     or "idle"
    total      = int(r.get(K_TOTAL)  or 0)
    done       = int(r.get(K_DONE)   or 0)
    current    = r.get(K_CURRENT)    or ""
    started_at = r.get(K_STARTED_AT) or ""

    elapsed = 0
    estimated = 0
    if started_at:
        try:
            dt      = datetime.fromisoformat(started_at)
            elapsed = int((datetime.now(timezone.utc) - dt).total_seconds())
            if done > 0 and elapsed > 0:
                rate      = done / elapsed           # 文档/秒
                estimated = int((total - done) / rate) if rate > 0 else 0
        except Exception:
            pass

    return {
        "status":                      status,
        "total":                       total,
        "done":                        done,
        "current_doc":                 current,
        "percent":                     round(done / total * 100, 1) if total > 0 else 0.0,
        "elapsed_seconds":             elapsed,
        "estimated_remaining_seconds": estimated,
    }


async def try_resume_on_startup() -> None:
    """
    在 FastAPI lifespan 中调用：
    1. 若 Redis 中 backfill:status 为 running/paused → 直接续跑（正常路径）
    2. 若 Redis 完全为空（容器重启导致 AOF 不可用等意外清空）→
       查询 Neo4j 待处理文档数，有则自动续跑（兜底路径）
    3. 若 status 为 completed/idle → 不做任何处理
    """
    r = _redis()
    status = r.get(K_STATUS)

    if status in ("running", "paused"):
        # ── 正常续跑路径 ──────────────────────────────────────────────────
        done  = int(r.get(K_DONE)  or 0)
        total = int(r.get(K_TOTAL) or 0)
        if total == 0:
            return
        logger.info(
            "[backfill] 检测到未完成任务 (done=%d/%d status=%s)，服务重启后自动续跑",
            done, total, status,
        )
        r.delete(K_PAUSE)
        try:
            await start_backfill(done_offset=done)
        except Exception as e:
            logger.warning("[backfill] 自动续跑失败: %s", e)

    elif status is None:
        # ── 兜底路径：Redis 无状态（可能被清空），查 Neo4j 判断是否有待处理工作 ──
        try:
            from ...core.database import get_driver
            driver  = get_driver()
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

    # status == "completed" / "idle" → 不处理
