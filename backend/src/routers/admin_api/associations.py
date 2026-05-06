"""
GET  /api/admin/associations        — 返回缓存的挖掘结果
POST /api/admin/associations/run    — 立即重新挖掘（后台任务）
POST /api/admin/associations/confirm — 确认建立显式关联
"""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, BackgroundTasks, Depends
from neo4j import Driver
from pydantic import BaseModel

from ...auth.deps import get_admin_user
from ...core.database import get_driver
from ...db.models import User
from ...services.infra.cache import get_redis

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/associations", tags=["admin"])

REDIS_KEY_DOC   = "mining:document_associations"
REDIS_KEY_META  = "mining:last_run"
REDIS_TTL       = 7 * 24 * 3600   # 7 天


def _run_mining(driver) -> None:
    from ...services.association_miner import AssociationMiner
    miner = AssociationMiner()
    results = miner.mine_document_associations(driver)
    r = get_redis()
    import time
    r.setex(REDIS_KEY_DOC,  REDIS_TTL, json.dumps(results,  ensure_ascii=False))
    r.setex(REDIS_KEY_META, REDIS_TTL, str(int(time.time())))
    logger.info("关联规则挖掘完成，发现 %d 组关联", len(results))


@router.get("")
async def get_associations(
    _: User = Depends(get_admin_user),
):
    r = get_redis()
    raw      = r.get(REDIS_KEY_DOC)
    last_run = r.get(REDIS_KEY_META)
    data     = json.loads(raw) if raw else []
    return {
        "associations": data,
        "total":        len(data),
        "implicit":     sum(1 for a in data if a.get("is_implicit")),
        "last_run":     int(last_run) if last_run else None,
    }


@router.post("/run")
async def run_mining(
    background_tasks: BackgroundTasks,
    _:      User   = Depends(get_admin_user),
    driver: Driver = Depends(get_driver),
):
    """在后台重新挖掘关联规则（可能需要数十秒）"""
    background_tasks.add_task(_run_mining, driver)
    return {"status": "started", "message": "挖掘任务已在后台启动"}


class ConfirmRequest(BaseModel):
    doc_a: str
    doc_b: str
    reason: str = "实体关联"


@router.post("/confirm")
async def confirm_association(
    req:    ConfirmRequest,
    _:      User   = Depends(get_admin_user),
    driver: Driver = Depends(get_driver),
):
    """在 Neo4j 中建立显式 RELATED_TO 关系"""
    with driver.session() as session:
        session.run(
            """
            MATCH (a:Document {name: $doc_a})
            MATCH (b:Document {name: $doc_b})
            MERGE (a)-[r:RELATED_TO]->(b)
            SET r.reason = $reason, r.source = 'association_mining'
            """,
            doc_a=req.doc_a,
            doc_b=req.doc_b,
            reason=req.reason,
        )
    logger.info("建立显式关联 %s <-> %s reason=%s", req.doc_a, req.doc_b, req.reason)
    return {"status": "ok", "doc_a": req.doc_a, "doc_b": req.doc_b}
