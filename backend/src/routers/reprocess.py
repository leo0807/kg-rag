"""
文档重新处理 API（需管理员权限）

POST   /api/documents/{doc_id}/reprocess           触发单文档重新处理
GET    /api/documents/{doc_id}/reprocess/status    查询进度
POST   /api/documents/{doc_id}/reprocess/cancel    中止处理
GET    /api/documents/{doc_id}/snapshots            列出可用快照
POST   /api/documents/{doc_id}/rollback/{snap_id}  回滚到指定快照
POST   /api/documents/reprocess-all                批量处理所有文档
GET    /api/documents/reprocess-all/status         批量进度
POST   /api/documents/reprocess-all/cancel         中止批量处理
POST   /api/documents/reprocess-all/resume         从断点续跑
"""
import asyncio
import logging
import time
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from neo4j import Driver

from ..core.database import get_driver
from ..auth.deps import get_admin_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["reprocess"])

_tasks:     dict[str, dict] = {}
_batch:     dict = {"status": "idle", "total": 0, "done": 0, "current_doc": "",
                    "errors": [], "completed_docs": [], "cancel_requested": False}

VALID = {"entities", "constraints", "tables", "drawings", "defects"}
ALL   = ["entities", "constraints", "tables", "drawings", "defects"]


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
        if not s.run("MATCH (d:Document {name:$d}) WHERE d.title IS NOT NULL RETURN d LIMIT 1", d=doc_id).single():
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
        from ..services.reprocess_service import reprocess_document
        await asyncio.to_thread(reprocess_document, doc_id, driver, pipelines, task)

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
    from ..services.snapshot_service import list_snapshots as _ls
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
        from ..services.snapshot_service import rollback as _rb
        result = await asyncio.to_thread(_rb, driver, doc_id, snapshot_id)
        return {"doc_id": doc_id, "rollback": result}
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


# ── 批量 ──────────────────────────────────────────────────────────────────────

class BatchReq(BaseModel):
    pipelines: list[str] = ALL


@router.post("/documents/reprocess-all")
async def reprocess_all(
    req:    BatchReq = BatchReq(),
    driver: Driver = Depends(get_driver),
    _admin = Depends(get_admin_user),
):
    if _batch.get("status") == "running":
        return {"status": "running", "message": "批量处理正在进行中"}

    pipelines = [p for p in req.pipelines if p in VALID]
    if not pipelines:
        raise HTTPException(400, f"无有效管道: {sorted(VALID)}")

    with driver.session() as s:
        doc_ids = [r["doc_id"] for r in s.run(
            "MATCH (d:Document) WHERE d.title IS NOT NULL RETURN d.name AS doc_id ORDER BY d.name"
        )]
    if not doc_ids:
        return {"status": "no_documents"}

    _batch.update({
        "status": "running", "total": len(doc_ids), "done": 0,
        "current_doc": "", "pipelines": pipelines, "errors": [],
        "completed_docs": [], "cancel_requested": False,
        "started_at": int(time.time()), "finished_at": None,
    })
    asyncio.create_task(_run_batch(doc_ids, pipelines, driver))
    return {"status": "started", "total": len(doc_ids), "pipelines": pipelines}


@router.get("/documents/reprocess-all/status")
async def batch_status(_admin = Depends(get_admin_user)):
    return _batch


@router.post("/documents/reprocess-all/cancel")
async def cancel_batch(_admin = Depends(get_admin_user)):
    if _batch.get("status") != "running":
        raise HTTPException(400, "无正在运行的批量任务")
    _batch["cancel_requested"] = True
    # 同时中止当前文档的单任务
    cur = _batch.get("current_doc", "")
    if cur and _tasks.get(cur, {}).get("status") == "running":
        _tasks[cur]["cancel_requested"] = True
    return {"message": "批量中止信号已发送"}


@router.post("/documents/reprocess-all/resume")
async def resume_batch(
    req:    BatchReq = BatchReq(),
    driver: Driver = Depends(get_driver),
    _admin = Depends(get_admin_user),
):
    if _batch.get("status") == "running":
        raise HTTPException(409, "批量任务仍在运行中")

    completed = set(_batch.get("completed_docs", []))
    pipelines = [p for p in req.pipelines if p in VALID] or (_batch.get("pipelines") or ALL)

    with driver.session() as s:
        all_ids = [r["doc_id"] for r in s.run(
            "MATCH (d:Document) WHERE d.title IS NOT NULL RETURN d.name AS doc_id ORDER BY d.name"
        )]
    remaining = [d for d in all_ids if d not in completed]
    if not remaining:
        return {"status": "all_done", "message": "所有文档已处理完毕"}

    _batch.update({
        "status": "running", "total": len(all_ids), "done": len(completed),
        "current_doc": "", "pipelines": pipelines, "cancel_requested": False,
        "started_at": int(time.time()), "finished_at": None,
    })
    asyncio.create_task(_run_batch(remaining, pipelines, driver))
    return {"status": "resumed", "remaining": len(remaining), "pipelines": pipelines}


# ── 内部批量执行 ───────────────────────────────────────────────────────────────

async def _run_batch(doc_ids: list[str], pipelines: list[str], driver):
    from ..services.reprocess_service import reprocess_document
    for doc_id in doc_ids:
        if _batch.get("cancel_requested"):
            break
        _batch["current_doc"] = doc_id
        task: dict = {
            "doc_id": doc_id, "status": "pending", "pipelines": pipelines,
            "current": "", "message": "", "results": {}, "error": "",
            "snapshot_id": None, "cancel_requested": False,
            "started_at": None, "finished_at": None,
        }
        _tasks[doc_id] = task
        try:
            await asyncio.to_thread(reprocess_document, doc_id, driver, pipelines, task)
            if task["status"] not in ("cancelled",):
                _batch["completed_docs"].append(doc_id)
        except Exception as e:
            _batch["errors"].append({"doc_id": doc_id, "error": str(e)})
        _batch["done"] += 1

    final = "cancelled" if _batch.get("cancel_requested") else "completed"
    _batch.update({"status": final, "current_doc": "", "finished_at": int(time.time())})
