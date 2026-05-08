"""
文档重新处理 API（需管理员权限）
"""
import asyncio
import logging
import time
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from neo4j import Driver

from ...core.database import get_driver
from ...auth.deps import get_admin_user
from .reprocess_handler import load_batch_state, save_batch_state, run_batch

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["reprocess"])

_tasks: dict[str, dict] = {}
_batch: dict = load_batch_state()

VALID = {"reparse", "vectorize", "images", "entities", "constraints", "tables", "drawings", "defects"}
ALL   = ["reparse", "vectorize", "images", "entities", "constraints", "tables", "drawings", "defects"]
ALIASES = {"reparse_sections": "reparse"}


def _normalize_pipeline(name: str) -> str:
    return ALIASES.get(name, name)


class ReprocessReq(BaseModel):
    pipelines: list[str] = ALL


class BatchReq(BaseModel):
    pipelines: list[str] = ALL
    doc_ids: list[str] | None = None


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
            "MATCH (d:Document {name:$d}) WHERE d.title IS NOT NULL RETURN d LIMIT 1", d=doc_id
        ).single():
            raise HTTPException(404, f"文档不存在: {doc_id}")

    if _tasks.get(doc_id, {}).get("status") == "running":
        return {"doc_id": doc_id, "status": "running", "message": "已有任务在运行"}

    pipelines = [_normalize_pipeline(p) for p in req.pipelines]
    pipelines = [p for p in pipelines if p in VALID]
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
            task.update({"status": "failed", "error": str(e), "finished_at": int(time.time())})
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
    doc_id: str, snapshot_id: str,
    driver: Driver = Depends(get_driver),
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


# ── 批量 ──────────────────────────────────────────────────────────────────────

@router.post("/documents/reprocess-all")
async def reprocess_all(
    req:    BatchReq = BatchReq(),
    driver: Driver   = Depends(get_driver),
    _admin = Depends(get_admin_user),
):
    global _batch
    if _batch.get("status") == "running":
        return {"status": "running", "message": "批量处理正在进行中",
                "total": _batch.get("total", 0), "done": _batch.get("done", 0)}

    pipelines = [_normalize_pipeline(p) for p in req.pipelines]
    pipelines = [p for p in pipelines if p in VALID]
    if not pipelines:
        raise HTTPException(400, f"无有效管道: {sorted(VALID)}")

    doc_ids = req.doc_ids
    if doc_ids is None:
        with driver.session() as s:
            doc_ids = [r["doc_id"] for r in s.run(
                "MATCH (d:Document) WHERE d.title IS NOT NULL RETURN d.name AS doc_id ORDER BY d.name"
            )]
    if not doc_ids:
        return {"status": "no_documents"}

    _batch = {
        "status": "running", "total": len(doc_ids), "done": 0,
        "current_doc": "", "current_step": "", "message": "启动中...",
        "pipelines": pipelines, "errors": [], "completed_docs": [],
        "cancel_requested": False, "started_at": int(time.time()), "finished_at": None,
    }
    save_batch_state(_batch)
    asyncio.create_task(run_batch(_batch, doc_ids, pipelines))
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
    driver: Driver   = Depends(get_driver),
    _admin = Depends(get_admin_user),
):
    global _batch
    if _batch.get("status") == "running":
        raise HTTPException(409, "批量任务仍在运行中")
    completed = set(_batch.get("completed_docs", []))
    pipelines = [_normalize_pipeline(p) for p in req.pipelines]
    pipelines = [p for p in pipelines if p in VALID] or ALL
    with driver.session() as s:
        all_ids = [r["doc_id"] for r in s.run(
            "MATCH (d:Document) WHERE d.title IS NOT NULL RETURN d.name AS doc_id ORDER BY d.name"
        )]
    remaining = [d for d in all_ids if d not in completed]
    if not remaining:
        return {"status": "all_done", "message": "所有文档已处理完毕"}
    _batch = {
        "status": "running", "total": len(all_ids), "done": len(completed),
        "current_doc": "", "current_step": "", "message": "续跑中...",
        "pipelines": pipelines, "errors": list(_batch.get("errors", [])),
        "completed_docs": list(completed), "cancel_requested": False,
        "started_at": int(time.time()), "finished_at": None,
    }
    save_batch_state(_batch)
    asyncio.create_task(run_batch(_batch, remaining, pipelines))
    return {"status": "resumed", "remaining": len(remaining),
            "skipped": len(completed), "pipelines": pipelines}


@router.post("/documents/reprocess-all/clear")
async def clear_batch(_admin = Depends(get_admin_user)):
    global _batch
    if _batch.get("status") == "running":
        raise HTTPException(400, "批量任务正在运行，请先中止再清除")
    _batch = {"status": "idle"}
    save_batch_state(_batch)
    return {"message": "批量任务状态已清除"}


def list_reprocess_tasks(limit: int = 20) -> list[dict]:
    rows = sorted(_tasks.values(),
                  key=lambda t: str(t.get("finished_at") or t.get("started_at") or ""), reverse=True)
    return rows[:max(limit, 1)]


def get_batch_task_snapshot() -> dict:
    return dict(_batch)
