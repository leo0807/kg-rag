"""
文档重新处理 API

POST /api/documents/{doc_id}/reprocess        — 对单个文档触发重新处理
GET  /api/documents/{doc_id}/reprocess/status — 查询处理进度
POST /api/documents/reprocess-all             — 批量重新处理所有文档
GET  /api/documents/reprocess-all/status      — 批量任务状态
"""
import asyncio
import logging
import time
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from neo4j import Driver
from ..core.database import get_driver

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["reprocess"])

# ── 进程内任务状态（单文档 + 批量）────────────────────────────────────────────
_tasks:      dict[str, dict] = {}   # doc_id → task dict
_batch_task: dict            = {"status": "idle", "total": 0, "done": 0,
                                 "current_doc": "", "errors": []}

VALID_PIPELINES = {"entities", "constraints", "tables", "drawings", "defects"}
DEFAULT_PIPELINES = ["entities", "constraints", "tables", "drawings", "defects"]


class ReprocessRequest(BaseModel):
    pipelines: list[str] = DEFAULT_PIPELINES


# ── 单文档重新处理 ─────────────────────────────────────────────────────────────

@router.post("/documents/{doc_id}/reprocess")
async def reprocess_document(
    doc_id: str,
    req:    ReprocessRequest = ReprocessRequest(),
    driver: Driver = Depends(get_driver),
):
    """
    对指定文档重新运行选定的处理管道，后台异步执行。
    可选管道: entities / constraints / tables / drawings / defects
    """
    # 文档存在性检查
    with driver.session() as session:
        rec = session.run(
            "MATCH (d:Document {name: $doc_id}) WHERE d.title IS NOT NULL RETURN d LIMIT 1",
            doc_id=doc_id,
        ).single()
    if not rec:
        raise HTTPException(404, f"文档不存在: {doc_id}")

    # 已在运行中则拒绝
    existing = _tasks.get(doc_id, {})
    if existing.get("status") == "running":
        return {"doc_id": doc_id, "status": "running", "message": "已有处理任务在运行中"}

    pipelines = [p for p in req.pipelines if p in VALID_PIPELINES]
    if not pipelines:
        raise HTTPException(400, f"无有效管道，支持: {sorted(VALID_PIPELINES)}")

    task: dict = {
        "doc_id":      doc_id,
        "status":      "pending",
        "pipelines":   pipelines,
        "current":     "",
        "message":     "等待启动...",
        "results":     {},
        "error":       "",
        "started_at":  None,
        "finished_at": None,
    }
    _tasks[doc_id] = task

    async def _run():
        from ..services.reprocess_service import reprocess_document as _reprocess
        await asyncio.to_thread(_reprocess, doc_id, driver, pipelines, task)

    asyncio.create_task(_run())
    return {"doc_id": doc_id, "status": "started", "pipelines": pipelines}


@router.get("/documents/{doc_id}/reprocess/status")
async def reprocess_status(doc_id: str):
    """查询指定文档的重新处理进度"""
    task = _tasks.get(doc_id)
    if not task:
        return {"doc_id": doc_id, "status": "idle"}
    return task


# ── 批量重新处理 ───────────────────────────────────────────────────────────────

class BatchReprocessRequest(BaseModel):
    pipelines: list[str] = DEFAULT_PIPELINES


@router.post("/documents/reprocess-all")
async def reprocess_all(
    req:    BatchReprocessRequest = BatchReprocessRequest(),
    driver: Driver = Depends(get_driver),
):
    """批量重新处理所有已入库文档（按顺序逐个执行）"""
    if _batch_task.get("status") == "running":
        return {"status": "running", "message": "批量处理正在进行中"}

    pipelines = [p for p in req.pipelines if p in VALID_PIPELINES]
    if not pipelines:
        raise HTTPException(400, f"无有效管道，支持: {sorted(VALID_PIPELINES)}")

    with driver.session() as session:
        result = session.run(
            "MATCH (d:Document) WHERE d.title IS NOT NULL RETURN d.name AS doc_id ORDER BY d.name"
        )
        doc_ids = [r["doc_id"] for r in result]

    if not doc_ids:
        return {"status": "no_documents", "message": "图谱中暂无文档"}

    _batch_task.update({
        "status":      "running",
        "total":       len(doc_ids),
        "done":        0,
        "current_doc": "",
        "pipelines":   pipelines,
        "errors":      [],
        "started_at":  int(time.time()),
        "finished_at": None,
    })

    async def _run_batch():
        from ..services.reprocess_service import reprocess_document as _reprocess
        for doc_id in doc_ids:
            _batch_task["current_doc"] = doc_id
            task: dict = {
                "doc_id": doc_id, "status": "pending",
                "pipelines": pipelines, "current": "",
                "message": "", "results": {}, "error": "",
                "started_at": None, "finished_at": None,
            }
            _tasks[doc_id] = task
            try:
                await asyncio.to_thread(_reprocess, doc_id, driver, pipelines, task)
            except Exception as e:
                _batch_task["errors"].append({"doc_id": doc_id, "error": str(e)})
            _batch_task["done"] += 1

        _batch_task.update({"status": "completed", "current_doc": "",
                             "finished_at": int(time.time())})

    asyncio.create_task(_run_batch())
    return {"status": "started", "total": len(doc_ids), "pipelines": pipelines}


@router.get("/documents/reprocess-all/status")
async def reprocess_all_status():
    """查询批量处理任务状态"""
    return _batch_task
