"""
文档重新处理 API（需管理员权限）

单文档 & 批量均使用 asyncio.create_task，在 FastAPI 进程内后台运行，
无需独立 Celery Worker。

端点：
POST   /api/documents/{doc_id}/reprocess           触发单文档重新处理
GET    /api/documents/{doc_id}/reprocess/status    查询进度
POST   /api/documents/{doc_id}/reprocess/cancel    中止处理
GET    /api/documents/{doc_id}/snapshots            列出可用快照
POST   /api/documents/{doc_id}/rollback/{snap_id}  回滚到指定快照
POST   /api/documents/reprocess-all                批量处理所有文档
GET    /api/documents/reprocess-all/status         批量进度
POST   /api/documents/reprocess-all/cancel         中止批量
POST   /api/documents/reprocess-all/resume         从断点续跑
"""
import asyncio
import json
import logging
import time
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from neo4j import Driver

from ...core.database import get_driver
from ...auth.deps import get_admin_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["reprocess"])

# ── 批量状态持久化（服务器重启后恢复进度）────────────────────────────────────────
_BATCH_STATE_FILE = Path("batch_state.json")

def _load_batch_state() -> dict:
    """启动时从文件恢复上次批量任务状态。"""
    try:
        if _BATCH_STATE_FILE.exists():
            state = json.loads(_BATCH_STATE_FILE.read_text(encoding="utf-8"))
            # 进程重启后，任务不可能还在 running，修正为 interrupted
            if state.get("status") == "running":
                state["status"] = "interrupted"
                state["message"] = '服务重启，任务被中断，可点击"续跑"继续'
            return state
    except Exception as e:
        logger.warning("批量状态文件读取失败: %s", e)
    return {"status": "idle"}

def _save_batch_state(state: dict) -> None:
    """将批量任务状态写入文件（异步安全，允许静默失败）。"""
    try:
        _BATCH_STATE_FILE.write_text(
            json.dumps(state, ensure_ascii=False, default=str), encoding="utf-8"
        )
    except Exception as e:
        logger.warning("批量状态文件写入失败: %s", e)

# ── 单文档任务（内存）─────────────────────────────────────────────────────────
_tasks: dict[str, dict] = {}

# ── 批量任务状态（进程内 + 持久化文件）─────────────────────────────────────────
_batch: dict = _load_batch_state()

VALID = {"reparse", "images", "entities", "constraints", "tables", "drawings", "defects"}
ALL   = ["reparse", "images", "entities", "constraints", "tables", "drawings", "defects"]


class ReprocessReq(BaseModel):
    pipelines: list[str] = ALL


# ── 单文档 ─────────────────────────────────────────────────────────────────────

@router.post("/documents/{doc_id}/reprocess")
async def reprocess_doc(
    doc_id: str,
    req:    ReprocessReq = ReprocessReq(),
    driver: Driver = Depends(get_driver),
    _admin = Depends(get_admin_user),
):
    with driver.session() as s:
        if not s.run(
            "MATCH (d:Document {name:$d}) WHERE d.title IS NOT NULL RETURN d LIMIT 1",
            d=doc_id,
        ).single():
            raise HTTPException(404, f"文档不存在: {doc_id}")

    if _tasks.get(doc_id, {}).get("status") == "running":
        return {"doc_id": doc_id, "status": "running", "message": "已有任务在运行"}

    pipelines = [p for p in req.pipelines if p in VALID]
    if not pipelines:
        raise HTTPException(400, f"无有效管道: {sorted(VALID)}")

    task: dict = {
        "doc_id": doc_id, "status": "pending", "pipelines": pipelines,
        "current": "", "message": "等待启动...", "results": {},
        "error": "", "snapshot_id": None,
        "cancel_requested": False, "started_at": None, "finished_at": None,
    }
    _tasks[doc_id] = task

    async def _run():
        try:
            from ...services.ingestion.reprocess_service import reprocess_document
            await asyncio.to_thread(reprocess_document, doc_id, driver, pipelines, task)
        except Exception as e:
            task.update({"status": "failed", "error": str(e),
                         "finished_at": int(time.time())})
            logger.error("[reprocess %s] 任务协程异常: %s", doc_id, e)

    asyncio.create_task(_run())
    return {"doc_id": doc_id, "status": "started", "pipelines": pipelines}


@router.get("/documents/{doc_id}/reprocess/status")
async def reprocess_status(doc_id: str, _admin = Depends(get_admin_user)):
    return _tasks.get(doc_id) or {"doc_id": doc_id, "status": "idle"}


@router.post("/documents/{doc_id}/reprocess/cancel")
async def cancel_reprocess(doc_id: str, _admin = Depends(get_admin_user)):
    task = _tasks.get(doc_id)
    if not task or task.get("status") not in ("running", "pending"):
        raise HTTPException(400, "无正在运行的任务")
    task["cancel_requested"] = True
    return {"doc_id": doc_id, "message": "中止信号已发送"}


# ── 快照 & 回滚 ───────────────────────────────────────────────────────────────

@router.get("/documents/{doc_id}/snapshots")
async def list_snapshots(doc_id: str, _admin = Depends(get_admin_user)):
    from ...services.ingestion.snapshot_service import list_snapshots as _ls
    return {"doc_id": doc_id, "snapshots": _ls(doc_id)}


@router.post("/documents/{doc_id}/rollback/{snapshot_id}")
async def rollback_doc(
    doc_id:      str,
    snapshot_id: str,
    driver:      Driver = Depends(get_driver),
    _admin = Depends(get_admin_user),
):
    if _tasks.get(doc_id, {}).get("status") == "running":
        raise HTTPException(409, "文档正在处理中，请先中止再回滚")
    try:
        from ...services.ingestion.snapshot_service import rollback as _rb
        result = await asyncio.to_thread(_rb, driver, doc_id, snapshot_id)
        return {"doc_id": doc_id, "rollback": result}
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


# ── 批量（asyncio 后台任务，无需 Celery Worker）───────────────────────────────

class BatchReq(BaseModel):
    pipelines: list[str] = ALL
    doc_ids: list[str] | None = None   # None = 处理所有文档；指定列表 = 只处理选中文档


async def _run_batch(doc_ids: list[str], pipelines: list[str]) -> None:
    """在 FastAPI 事件循环内后台运行批量重处理，逐文档顺序执行。"""
    global _batch
    from ...services.ingestion.reprocess_service import reprocess_document

    driver = get_driver()
    total  = len(doc_ids)
    done   = 0
    errors: list[dict] = []
    completed_docs: list[str] = []

    def _update(**kw):
        _batch.update(kw)

    def _update_and_save(**kw):
        _batch.update(kw)
        _save_batch_state(_batch)

    try:
        for doc_id in doc_ids:
            if _batch.get("cancel_requested"):
                break

            _update(current_doc=doc_id, message="准备处理...",
                    done=done, errors=errors, completed_docs=completed_docs)

            task_proxy: dict = {
                "doc_id": doc_id, "status": "pending", "pipelines": pipelines,
                "current": "", "message": "", "results": {}, "error": "",
                "snapshot_id": None, "cancel_requested": False,
                "started_at": None, "finished_at": None,
            }

            def _on_step(name: str, msg: str):
                _update(current_step=name, message=msg)

            try:
                await asyncio.to_thread(
                    reprocess_document, doc_id, driver, pipelines, task_proxy, _on_step
                )
                if task_proxy.get("status") != "cancelled":
                    completed_docs.append(doc_id)
            except Exception as exc:
                logger.error("批量重处理文档 %s 失败: %s", doc_id, exc, exc_info=True)
                errors.append({"doc_id": doc_id, "error": str(exc)})

            done += 1
            # 每完成一个文档持久化进度（支持重启续跑）
            _update_and_save(done=done, errors=errors, completed_docs=completed_docs)

        was_cancelled = bool(_batch.get("cancel_requested"))
        _update_and_save(**{
            "status":         "cancelled" if was_cancelled else "completed",
            "done":           done,
            "current_doc":    "",
            "message":        "已中止" if was_cancelled else "全部完成",
            "errors":         errors,
            "completed_docs": completed_docs,
            "finished_at":    int(time.time()),
        })

    except Exception as exc:
        logger.error("批量重处理整体异常: %s", exc, exc_info=True)
        _update_and_save(**{
            "status": "failed", "message": str(exc),
            "finished_at": int(time.time()),
        })


@router.post("/documents/reprocess-all")
async def reprocess_all(
    req:    BatchReq = BatchReq(),
    driver: Driver = Depends(get_driver),
    _admin = Depends(get_admin_user),
):
    global _batch

    if _batch.get("status") == "running":
        return {"status": "running", "message": "批量处理正在进行中",
                "total": _batch.get("total", 0), "done": _batch.get("done", 0)}

    pipelines = [p for p in req.pipelines if p in VALID]
    if not pipelines:
        raise HTTPException(400, f"无有效管道: {sorted(VALID)}")

    # 若前端传了 doc_ids，则只处理选中的文档；否则处理全部
    if req.doc_ids is not None:
        doc_ids = req.doc_ids
    else:
        with driver.session() as s:
            doc_ids = [r["doc_id"] for r in s.run(
                "MATCH (d:Document) WHERE d.title IS NOT NULL RETURN d.name AS doc_id ORDER BY d.name"
            )]
    if not doc_ids:
        return {"status": "no_documents"}

    _batch = {
        "status":         "running",
        "total":          len(doc_ids),
        "done":           0,
        "current_doc":    "",
        "current_step":   "",
        "message":        "启动中...",
        "pipelines":      pipelines,
        "errors":         [],
        "completed_docs": [],
        "cancel_requested": False,
        "started_at":     int(time.time()),
        "finished_at":    None,
    }
    _save_batch_state(_batch)

    asyncio.create_task(_run_batch(doc_ids, pipelines))
    return {"status": "started", "total": len(doc_ids), "pipelines": pipelines}


@router.get("/documents/reprocess-all/status")
async def batch_status(_admin = Depends(get_admin_user)):
    return _batch


@router.post("/documents/reprocess-all/cancel")
async def cancel_batch(_admin = Depends(get_admin_user)):
    if _batch.get("status") != "running":
        raise HTTPException(400, "无正在运行的批量任务")
    _batch["cancel_requested"] = True
    return {"message": "批量中止信号已发送"}


@router.post("/documents/reprocess-all/resume")
async def resume_batch(
    req:    BatchReq = BatchReq(),
    driver: Driver = Depends(get_driver),
    _admin = Depends(get_admin_user),
):
    global _batch

    if _batch.get("status") == "running":
        raise HTTPException(409, "批量任务仍在运行中")

    completed = set(_batch.get("completed_docs", []))
    pipelines = [p for p in req.pipelines if p in VALID] or ALL

    with driver.session() as s:
        all_ids = [r["doc_id"] for r in s.run(
            "MATCH (d:Document) WHERE d.title IS NOT NULL RETURN d.name AS doc_id ORDER BY d.name"
        )]

    remaining = [d for d in all_ids if d not in completed]
    if not remaining:
        return {"status": "all_done", "message": "所有文档已处理完毕"}

    _batch = {
        "status":         "running",
        "total":          len(all_ids),
        "done":           len(completed),
        "current_doc":    "",
        "current_step":   "",
        "message":        "续跑中...",
        "pipelines":      pipelines,
        "errors":         list(_batch.get("errors", [])),
        "completed_docs": list(completed),
        "cancel_requested": False,
        "started_at":     int(time.time()),
        "finished_at":    None,
    }
    _save_batch_state(_batch)

    asyncio.create_task(_run_batch(remaining, pipelines))
    return {"status": "resumed", "remaining": len(remaining),
            "skipped": len(completed), "pipelines": pipelines}


@router.post("/documents/reprocess-all/clear")
async def clear_batch(_admin = Depends(get_admin_user)):
    """重置批量任务状态为 idle（运行中不允许清除）。"""
    global _batch
    if _batch.get("status") == "running":
        raise HTTPException(400, "批量任务正在运行，请先中止再清除")
    _batch = {"status": "idle"}
    _save_batch_state(_batch)
    return {"message": "批量任务状态已清除"}


def list_reprocess_tasks(limit: int = 20) -> list[dict]:
    rows = sorted(
        _tasks.values(),
        key=lambda task: str(task.get("finished_at") or task.get("started_at") or ""),
        reverse=True,
    )
    return rows[: max(limit, 1)]


def get_batch_task_snapshot() -> dict:
    return dict(_batch)
