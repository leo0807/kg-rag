"""
H4.1 ERP 系统接入器（SAP / 用友 / 金蝶通用 REST 适配）
"""
from __future__ import annotations

import logging
from typing import Any

from .base import ApiKeyProvider, IntegrationError

logger = logging.getLogger(__name__)


class ERPProvider(ApiKeyProvider):
    """通用 ERP REST 接入器。"""

    async def get_material_info(self, material_code: str) -> dict | None:
        try:
            return await self.call("GET", f"/api/materials/{material_code}")
        except IntegrationError as e:
            logger.warning("ERP get_material_info(%s) failed: %s", material_code, e)
            return None

    async def get_material_stock(self, material_code: str) -> dict | None:
        """获取物料库存信息。"""
        try:
            return await self.call("GET", f"/api/materials/{material_code}/stock")
        except IntegrationError as e:
            logger.warning("ERP get_material_stock(%s) failed: %s", material_code, e)
            return None

    async def search_substitute_materials(self, material_code: str) -> list[dict]:
        """查询可替代物料列表。"""
        try:
            data = await self.call(
                "GET", f"/api/materials/{material_code}/substitutes"
            )
            return data if isinstance(data, list) else data.get("items", [])
        except IntegrationError as e:
            logger.warning("ERP search_substitute_materials(%s) failed: %s", material_code, e)
            return []

    async def get_supplier_info(self, supplier_code: str) -> dict | None:
        try:
            return await self.call("GET", f"/api/suppliers/{supplier_code}")
        except IntegrationError as e:
            logger.warning("ERP get_supplier_info(%s) failed: %s", supplier_code, e)
            return None

    async def get_purchase_orders(self, material_code: str) -> list[dict]:
        try:
            data = await self.call(
                "GET", "/api/purchase-orders",
                params={"material_code": material_code}
            )
            return data if isinstance(data, list) else data.get("items", [])
        except IntegrationError as e:
            logger.warning("ERP get_purchase_orders(%s) failed: %s", material_code, e)
            return []

    async def test_connection(self) -> bool:
        try:
            await self.call("GET", self.auth_config.get("health_path", "/api/health"))
            return True
        except IntegrationError:
            return False


# ── H4.2 物料替代顾问 ──────────────────────────────────────────────────

import re

_MATERIAL_CODE_RE = re.compile(
    r"\b([A-Z0-9]{2,6}-[A-Z0-9]{3,10}|[0-9]{6,12})\b"
)


class MaterialAdvisor:
    """当规范中要求某材料而 ERP 显示缺货时，提示可替代材料。"""

    def __init__(self, provider: ERPProvider):
        self.provider = provider

    def extract_material_codes(self, text: str) -> list[str]:
        return list(dict.fromkeys(_MATERIAL_CODE_RE.findall(text.upper())))

    async def advise(self, question: str, answer_draft: str) -> list[dict]:
        """
        分析答案草稿中的物料编码，查询 ERP 库存，
        对缺货物料返回替代建议。
        """
        codes = self.extract_material_codes(answer_draft)
        if not codes:
            return []

        advisories: list[dict] = []
        for code in codes[:5]:
            stock = await self.provider.get_material_stock(code)
            if stock is None:
                continue

            available = stock.get("available_qty", 0)
            if available > 0:
                continue  # 有库存，无需替代

            subs = await self.provider.search_substitute_materials(code)
            if not subs:
                advisories.append({
                    "material_code": code,
                    "stock": available,
                    "message": f"物料 {code} 当前缺货，暂无替代料信息",
                    "substitutes": [],
                })
            else:
                advisories.append({
                    "material_code": code,
                    "stock": available,
                    "message": f"物料 {code} 缺货，以下替代料可供参考：",
                    "substitutes": [
                        {
                            "code": s.get("code"),
                            "name": s.get("name"),
                            "stock": s.get("available_qty", 0),
                        }
                        for s in subs[:3]
                    ],
                })

        return advisories
