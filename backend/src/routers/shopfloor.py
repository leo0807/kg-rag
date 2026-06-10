"""
H3.2 工位问答增强端点
POST /api/shopfloor/query — 携带工位/工单上下文的精准问答
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import get_current_user
from ..db.integration_models import Integration
from ..db.models import User
from ..db.session import get_db
from ..services.integration.mes_provider import MESProvider, ShopfloorContext
from ..services.multitenant.tenant_filter import get_tenant_id_optional

router = APIRouter(prefix="/api/shopfloor", tags=["shopfloor"])
logger = logging.getLogger(__name__)


class ShopfloorQuery(BaseModel):
    question: str
    station_id: str | None = None
    work_order_id: str | None = None
    operator_id: str | None = None
    # 可选：限定文档范围
    doc_filter: list[str] = []


async def _get_mes_provider(
    db: AsyncSession, tenant_id: str | None
) -> MESProvider | None:
    """查找并构建租户的 MES 接入器。"""
    stmt = select(Integration).where(
        Integration.type == "mes",
        Integration.status == "active",
    )
    if tenant_id:
        stmt = stmt.where(Integration.tenant_id == tenant_id)
    obj = (await db.execute(stmt.limit(1))).scalar_one_or_none()
    if not obj:
        return None
    return MESProvider(
        integration_id=obj.id,
        endpoint=obj.endpoint or "",
        auth_config=obj.auth_config or {},
    )


@router.post("/query")
async def shopfloor_query(
    body: ShopfloorQuery,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    现场问答：自动注入 MES 工单/工位上下文，限定相关规范范围。
    若 MES 不可用则降级为普通问答。
    """
    tid = get_tenant_id_optional(request)
    extra_sources: list[dict] = []

    # 注入 MES 上下文（失败不阻断）
    try:
        provider = await _get_mes_provider(db, tid)
        if provider and (body.station_id or body.work_order_id):
            ctx = ShopfloorContext(provider)
            extra_sources = await ctx.build(body.station_id, body.work_order_id)
    except Exception as exc:
        logger.warning("MES context fetch failed (degraded): %s", exc)

    # 组装增强 prompt 前缀
    context_text = ""
    if extra_sources:
        context_text = "\n\n".join(s["content"] for s in extra_sources)

    operator_info = f"操作者: {body.operator_id}" if body.operator_id else ""
    station_info  = f"工位: {body.station_id}"    if body.station_id   else ""
    prefix = " | ".join(filter(None, [operator_info, station_info]))

    return {
        "question": body.question,
        "context_prefix": prefix,
        "mes_context": extra_sources,
        "mes_context_text": context_text,
        "doc_filter": body.doc_filter,
        "work_order_id": body.work_order_id,
        "station_id": body.station_id,
        "note": "请将 mes_context_text 和 question 合并后送入 /api/query/stream",
    }


@router.get("/work-orders/{wo_id}")
async def get_work_order_context(
    wo_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """前端工位扫码后获取工单概要。"""
    tid = get_tenant_id_optional(request)
    provider = await _get_mes_provider(db, tid)
    if not provider:
        raise HTTPException(503, "MES 集成未配置")
    wo = await provider.get_work_order(wo_id)
    if not wo:
        raise HTTPException(404, "工单不存在")
    return wo
