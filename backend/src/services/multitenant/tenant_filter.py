"""
G2.2 数据访问自动过滤
TenantQueryMixin — SQLAlchemy 模型混入，自动注入 tenant_id 过滤
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from sqlalchemy.orm import DeclarativeBase


class TenantQueryMixin:
    """继承此 mixin 的模型可使用 query_for_tenant 快速过滤。"""

    @classmethod
    def query_for_tenant(cls, session: AsyncSession, tenant_id: str):
        return session.execute(
            select(cls).where(cls.tenant_id == tenant_id)  # type: ignore[attr-defined]
        )

    @classmethod
    def filter_stmt(cls, stmt: Any, tenant_id: str) -> Any:
        return stmt.where(cls.tenant_id == tenant_id)  # type: ignore[attr-defined]


def get_tenant_id(request: Request) -> str:
    """从请求状态中提取 tenant_id，不存在时抛 403。"""
    tid = getattr(request.state, "tenant_id", None)
    if not tid:
        raise HTTPException(status_code=403, detail="缺少租户上下文")
    return tid


def get_tenant_id_optional(request: Request) -> str | None:
    """从请求状态中提取 tenant_id，允许为空。"""
    return getattr(request.state, "tenant_id", None)


def build_milvus_tenant_expr(tenant_id: str, original_expr: str = "") -> str:
    """为 Milvus 搜索构造 tenant_id 过滤表达式。"""
    base = f'tenant_id == "{tenant_id}"'
    if original_expr:
        return f"({original_expr}) and {base}"
    return base


def inject_neo4j_tenant(params: dict, tenant_id: str) -> dict:
    """在 Neo4j 查询参数中注入 tenant_id。"""
    return {**params, "tenant_id": tenant_id}
