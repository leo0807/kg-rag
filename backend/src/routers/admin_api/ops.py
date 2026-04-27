from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from neo4j import Driver
from pydantic import BaseModel, Field
from ...core.config import settings as _cfg
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.deps import get_admin_user
from ...core.database import get_driver
from ...db.models import User
from ...db.session import get_db
from ...services.evaluation.retrieval_harness_service import (
    get_retrieval_task,
    start_retrieval_harness,
)
from ...services.ops.audit_service import append_audit_log
from ...services.ops.harness_service import builtin_retrieval_cases_path, run_harness_query
from ...services.ops.runtime_service import build_ops_overview, list_runtime_tasks

router = APIRouter(prefix="/api/admin/ops", tags=["admin"])


class HarnessQueryRequest(BaseModel):
    question: str = Field(min_length=1)
    doc_id: str = ""
    top_k: int = Field(default=5, ge=1, le=10)
    strategy: str = ""


class BaselineRunRequest(BaseModel):
    strategy: str = "parallel"
    top_k: int = Field(default=5, ge=1, le=10)


@router.get("/overview")
async def ops_overview(
    driver: Driver = Depends(get_driver),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    return await build_ops_overview(driver, db)


@router.get("/runtime")
async def runtime_tasks(
    limit: int = 30,
    _: User = Depends(get_admin_user),
):
    return {"items": list_runtime_tasks(limit=limit)}


@router.post("/harness/query")
async def harness_query(
    req: HarnessQueryRequest,
    driver: Driver = Depends(get_driver),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    result = run_harness_query(
        driver,
        question=req.question,
        top_k=req.top_k,
        doc_id=req.doc_id,
        strategy=req.strategy,
    )
    await append_audit_log(
        db,
        user=admin,
        action="run_ops_harness",
        resource="admin_ops",
        detail=(
            f"question={req.question[:80]} | strategy={result['plan']['strategy']} | "
            f"doc_id={req.doc_id or '-'} | sections={result['runtime']['section_hits']} | "
            f"images={result['runtime']['image_hits']}"
        ),
    )
    return result


@router.post("/retrieval-baseline/run")
async def run_retrieval_baseline(
    req: BaselineRunRequest,
    driver: Driver = Depends(get_driver),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    sample_path = builtin_retrieval_cases_path()
    if not sample_path.exists():
        raise HTTPException(status_code=404, detail="仓库内置 retrieval case 不存在")

    task = await start_retrieval_harness(
        filename=sample_path.name,
        data=sample_path.read_bytes(),
        strategy=req.strategy,
        top_k=req.top_k,
        driver=driver,
    )
    await append_audit_log(
        db,
        user=admin,
        action="run_retrieval_baseline",
        resource="admin_ops",
        detail=(
            f"task_id={task['task_id']} | strategy={req.strategy} | top_k={req.top_k} | "
            f"file={sample_path.name}"
        ),
    )
    return task


@router.get("/retrieval-baseline/{task_id}")
async def get_retrieval_baseline_task(
    task_id: str,
    _: User = Depends(get_admin_user),
):
    try:
        return get_retrieval_task(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="检索基线任务不存在") from exc


# ── 混合检索 alpha 配置 ───────────────────────────────────────────────────────

HYBRID_ALPHA_KEY = "search:hybrid_alpha"
_DEFAULT_ALPHA = 0.5


class HybridAlphaRequest(BaseModel):
    alpha: float = Field(ge=0.0, le=1.0)


def _get_redis():
    import redis
    return redis.from_url(_cfg.REDIS_URL)


@router.get("/hybrid-alpha")
async def get_hybrid_alpha(_: User = Depends(get_admin_user)):
    try:
        r = _get_redis()
        v = r.get(HYBRID_ALPHA_KEY)
        alpha = float(v) if v else _DEFAULT_ALPHA
    except Exception:
        alpha = _DEFAULT_ALPHA
    return {"alpha": alpha}


@router.put("/hybrid-alpha")
async def set_hybrid_alpha(
    req: HybridAlphaRequest,
    _: User = Depends(get_admin_user),
):
    try:
        r = _get_redis()
        r.set(HYBRID_ALPHA_KEY, str(req.alpha))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Redis 写入失败: {exc}") from exc
    return {"alpha": req.alpha, "saved": True}
