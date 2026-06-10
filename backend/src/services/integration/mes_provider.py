"""
H3.1 MES 系统接入器
"""
from __future__ import annotations

import logging
from typing import Any

from .base import ApiKeyProvider, IntegrationError

logger = logging.getLogger(__name__)


class MESProvider(ApiKeyProvider):
    """通用 MES REST 接入器（工单/工位/质量）。"""

    async def get_work_orders(self, status: str = "active") -> list[dict]:
        try:
            data = await self.call("GET", "/api/work-orders", params={"status": status})
            return data if isinstance(data, list) else data.get("items", [])
        except IntegrationError as e:
            logger.warning("MES get_work_orders failed: %s", e)
            return []

    async def get_work_order(self, wo_id: str) -> dict | None:
        try:
            return await self.call("GET", f"/api/work-orders/{wo_id}")
        except IntegrationError as e:
            logger.warning("MES get_work_order(%s) failed: %s", wo_id, e)
            return None

    async def get_current_operations(self, station_id: str) -> list[dict]:
        try:
            data = await self.call("GET", f"/api/stations/{station_id}/operations")
            return data if isinstance(data, list) else data.get("items", [])
        except IntegrationError as e:
            logger.warning("MES get_current_operations(%s) failed: %s", station_id, e)
            return []

    async def get_process_route(self, wo_id: str) -> dict | None:
        """获取工单的工艺路线。"""
        try:
            return await self.call("GET", f"/api/work-orders/{wo_id}/process-route")
        except IntegrationError as e:
            logger.warning("MES get_process_route(%s) failed: %s", wo_id, e)
            return None

    async def report_quality_issue(self, issue: dict) -> dict | None:
        """上报质量问题（不阻断主流程）。"""
        try:
            return await self.call("POST", "/api/quality/issues", json=issue)
        except IntegrationError as e:
            logger.warning("MES report_quality_issue failed: %s", e)
            return None

    async def query_production_data(self, criteria: dict) -> list[dict]:
        try:
            data = await self.call("POST", "/api/production/query", json=criteria)
            return data if isinstance(data, list) else data.get("items", [])
        except IntegrationError as e:
            logger.warning("MES query_production_data failed: %s", e)
            return []

    async def test_connection(self) -> bool:
        try:
            await self.call("GET", self.auth_config.get("health_path", "/api/health"))
            return True
        except IntegrationError:
            return False


def _format_work_order(wo: dict) -> str:
    lines = [f"[MES 工单] 工单号: {wo.get('id', '—')}"]
    if wo.get("product"):
        lines.append(f"  产品: {wo['product']}")
    if wo.get("operation"):
        lines.append(f"  当前工序: {wo['operation']}")
    if wo.get("station"):
        lines.append(f"  工位: {wo['station']}")
    if wo.get("process_route"):
        lines.append(f"  工艺路线: {wo['process_route']}")
    if wo.get("quality_requirements"):
        lines.append(f"  质量要求: {wo['quality_requirements']}")
    return "\n".join(lines)


class ShopfloorContext:
    """组装车间现场问答上下文。"""

    def __init__(self, provider: MESProvider):
        self.provider = provider

    async def build(
        self,
        station_id: str | None,
        work_order_id: str | None,
    ) -> list[dict]:
        """返回与当前工位/工单相关的 MES 上下文 sources。"""
        sources: list[dict] = []

        if work_order_id:
            wo = await self.provider.get_work_order(work_order_id)
            if wo:
                sources.append({
                    "type": "mes_work_order",
                    "content": _format_work_order(wo),
                    "source": "MES",
                    "work_order_id": work_order_id,
                })

        if station_id:
            ops = await self.provider.get_current_operations(station_id)
            for op in ops[:3]:
                sources.append({
                    "type": "mes_operation",
                    "content": f"[工位操作] {op.get('name', '')}：{op.get('description', '')}",
                    "source": "MES",
                })

        return sources
