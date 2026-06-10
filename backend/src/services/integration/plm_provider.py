"""
H2.1 PLM 系统接入器
支持 Teamcenter / Windchill / 华三PLM（通用 REST 适配）
"""
from __future__ import annotations

import logging
from typing import Any

from .base import ApiKeyProvider, IntegrationError

logger = logging.getLogger(__name__)


class PLMProvider(ApiKeyProvider):
    """通用 PLM REST 接入器。"""

    async def search_parts(self, query: str, doc_id: str | None = None) -> list[dict]:
        """搜索零件信息。"""
        try:
            params: dict = {"q": query}
            if doc_id:
                params["doc_id"] = doc_id
            data = await self.call("GET", "/api/parts/search", params=params)
            return data if isinstance(data, list) else data.get("items", [])
        except IntegrationError as e:
            logger.warning("PLM search_parts failed: %s", e)
            return []

    async def get_part_detail(self, part_no: str) -> dict | None:
        """获取零件详情。"""
        try:
            return await self.call("GET", f"/api/parts/{part_no}")
        except IntegrationError as e:
            logger.warning("PLM get_part_detail(%s) failed: %s", part_no, e)
            return None

    async def get_bom(self, product_id: str) -> dict | None:
        """获取产品 BOM 树。"""
        try:
            return await self.call("GET", f"/api/products/{product_id}/bom")
        except IntegrationError as e:
            logger.warning("PLM get_bom(%s) failed: %s", product_id, e)
            return None

    async def get_drawing(self, drawing_id: str) -> dict | None:
        """获取工程图纸元数据（不下载文件）。"""
        try:
            return await self.call("GET", f"/api/drawings/{drawing_id}")
        except IntegrationError as e:
            logger.warning("PLM get_drawing(%s) failed: %s", drawing_id, e)
            return None

    async def list_drawings_for_product(self, product_id: str) -> list[dict]:
        """列出产品的所有关联图纸。"""
        try:
            data = await self.call("GET", f"/api/products/{product_id}/drawings")
            return data if isinstance(data, list) else data.get("items", [])
        except IntegrationError:
            return []

    async def test_connection(self) -> bool:
        try:
            await self.call("GET", self.auth_config.get("health_path", "/api/health"))
            return True
        except IntegrationError:
            return False


def _format_part_info(part: dict) -> str:
    """将零件字典格式化为可插入 prompt 的文本。"""
    lines = [f"[PLM 零件信息] 零件号: {part.get('part_no', '—')}"]
    if part.get("name"):
        lines.append(f"  名称: {part['name']}")
    if part.get("material"):
        lines.append(f"  材料: {part['material']}")
    if part.get("drawing_no"):
        lines.append(f"  图号: {part['drawing_no']}")
    if part.get("revision"):
        lines.append(f"  版本: {part['revision']}")
    if part.get("status"):
        lines.append(f"  状态: {part['status']}")
    if part.get("description"):
        lines.append(f"  描述: {part['description']}")
    return "\n".join(lines)


# ── H2.2 PLM 信息融合 ─────────────────────────────────────────────────

import re

# 常见零件号格式：字母+数字组合，如 A1234、XX-1234-01
_PART_NO_RE = re.compile(r"\b([A-Z]{1,4}[-_]?\d{3,10}(?:[-_]\d{1,4})?)\b")


class PLMEnricher:
    """从 PLM 补充零件信息，作为检索上下文增强。"""

    def __init__(self, provider: PLMProvider):
        self.provider = provider

    def extract_part_nos(self, text: str) -> list[str]:
        return list(dict.fromkeys(_PART_NO_RE.findall(text.upper())))

    async def enrich(self, question: str, sources: list[dict]) -> list[dict]:
        """提取零件号并追加 PLM 信息到 sources。"""
        part_nos = self.extract_part_nos(question)
        if not part_nos:
            return sources

        enriched = list(sources)
        for pno in part_nos[:5]:  # 最多补充 5 个零件
            part = await self.provider.get_part_detail(pno)
            if part:
                enriched.append({
                    "type": "plm_part",
                    "content": _format_part_info(part),
                    "source": "PLM",
                    "part_no": pno,
                })
        return enriched


# ── H2.3 图纸同步（简化实现）────────────────────────────────────────────

async def sync_plm_drawings(provider: PLMProvider, product_ids: list[str]) -> dict:
    """同步 PLM 图纸到 Neo4j（占位：返回待同步条目）。"""
    synced, failed = 0, 0
    items: list[dict] = []

    for pid in product_ids:
        drawings = await provider.list_drawings_for_product(pid)
        for d in drawings:
            items.append({
                "product_id": pid,
                "drawing_id": d.get("id"),
                "drawing_no": d.get("drawing_no"),
                "title": d.get("title"),
            })
            synced += 1

    return {"synced": synced, "failed": failed, "items": items}
