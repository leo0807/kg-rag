"""
章节生成器 — 每种章节使用专门的检索+提示策略。
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from ...prompts import registry
from ...services.ai.llm_service import get_llm_service

logger = logging.getLogger(__name__)

# ── 参考内容检索 ─────────────────────────────────────────────────────────────

def _retrieve_section_content(driver, doc_ids: list[str], title_keywords: list[str], max_chars: int = 2000) -> str:
    """从 Neo4j 检索指定文档中匹配标题关键词的章节内容。"""
    if not doc_ids or not driver:
        return ""
    kw_conditions = " OR ".join(f"s.title CONTAINS '{kw}'" for kw in title_keywords)
    query = f"""
    MATCH (d:Document)-[:HAS_SECTION]->(s:Section)
    WHERE d.name IN $doc_ids AND ({kw_conditions})
    RETURN d.name AS doc_id, s.title AS title, s.content AS content
    ORDER BY d.name, s.section_number
    LIMIT 8
    """
    try:
        with driver.session() as sess:
            result = sess.run(query, doc_ids=doc_ids)
            parts = []
            for r in result:
                title = r["title"] or ""
                content = (r["content"] or "")[:max_chars // 4]
                parts.append(f"【{r['doc_id']} {title}】\n{content}")
            return "\n\n".join(parts)[:max_chars]
    except Exception as e:
        logger.warning("_retrieve_section_content failed: %s", e)
        return ""


def _format_test_data(test_data: dict | None) -> str:
    if not test_data:
        return "（无试验数据）"
    rows = test_data.get("rows", [])
    if not rows:
        return "（无试验数据）"
    lines = [f"- {r.get('parameter','')}: {r.get('value','')} {r.get('unit','')}  [{r.get('condition','')}]"
             for r in rows[:20]]
    return "\n".join(lines)


def _build_refs_text(doc_ids: list[str], must_reference: list[str]) -> str:
    lines = []
    for d in doc_ids:
        lines.append(f"- {d}")
    for r in must_reference:
        lines.append(f"- {r}（必引）")
    return "\n".join(lines) if lines else "（无指定参考文件）"


# ── LLM 调用封装 ─────────────────────────────────────────────────────────────

def _chat_sync(template_id: str, **variables: str) -> str:
    rendered = registry.render(template_id, **variables)
    llm = get_llm_service()
    return llm.chat(rendered["messages"], max_tokens=rendered["max_tokens"])


async def _chat_async(template_id: str, **variables: str) -> str:
    return await asyncio.to_thread(_chat_sync, template_id, **variables)


# ── 章节生成器 ────────────────────────────────────────────────────────────────

class SectionGenerator:
    """按章节类型分发生成策略，每章节单独调用 LLM。"""

    def __init__(self, driver=None):
        self._driver = driver

    async def generate_scope(self, inputs: dict, ref_content: str = "") -> str:
        return await _chat_async(
            "gen_scope",
            spec_name=inputs.get("spec_name", ""),
            spec_type=inputs.get("spec_type", ""),
            reference_sections=ref_content or "（无参考）",
            user_requirements=inputs.get("user_requirements", ""),
            target_application=inputs.get("target_application", ""),
        )

    async def generate_refs(self, inputs: dict) -> str:
        doc_ids = inputs.get("reference_docs", [])
        must_ref = inputs.get("must_reference", [])
        refs_text = _build_refs_text(doc_ids, must_ref)
        spec_name = inputs.get("spec_name", "")
        spec_type = inputs.get("spec_type", "")
        prompt = (
            f"请为规范《{spec_name}》（{spec_type}类）"
            f"生成\"2 引用文件\"章节。\n"
            f"已知应引用的文件：\n{refs_text}\n\n"
            f"格式：每条一行，编号格式 2.X，给出文件编号和名称。"
        )
        llm = get_llm_service()
        return await asyncio.to_thread(
            llm.chat, [{"role": "user", "content": prompt}], max_tokens=400
        )

    async def generate_terms(self, inputs: dict, ref_content: str = "") -> str:
        return await _chat_async(
            "gen_terms",
            spec_name=inputs.get("spec_name", ""),
            spec_type=inputs.get("spec_type", ""),
            reference_terms=ref_content or "（无参考）",
            user_requirements=inputs.get("user_requirements", ""),
        )

    async def generate_materials(self, inputs: dict) -> str:
        prompt = (
            f"请为规范《{inputs.get('spec_name','')}》（{inputs.get('spec_type','')}类）"
            f"生成\"4 材料\"章节。\n"
            f"要求：列出主要材料及执行标准，格式：4.X 材料名称（牌号/规格） 执行标准编号。"
        )
        llm = get_llm_service()
        return await asyncio.to_thread(
            llm.chat, [{"role": "user", "content": prompt}], max_tokens=400
        )

    async def generate_requirements(self, inputs: dict, ref_content: str = "") -> str:
        test_data = inputs.get("test_data") or {}
        return await _chat_async(
            "gen_requirements",
            spec_name=inputs.get("spec_name", ""),
            spec_type=inputs.get("spec_type", ""),
            reference_requirements=ref_content or "（无参考）",
            test_data_summary=_format_test_data(test_data),
            user_requirements=inputs.get("user_requirements", ""),
        )

    async def generate_process(self, inputs: dict, ref_content: str = "") -> str:
        test_data = inputs.get("test_data") or {}
        return await _chat_async(
            "gen_process",
            spec_name=inputs.get("spec_name", ""),
            spec_type=inputs.get("spec_type", ""),
            reference_process=ref_content or "（无参考）",
            test_data_summary=_format_test_data(test_data),
            user_requirements=inputs.get("user_requirements", ""),
        )

    async def generate_inspection(self, inputs: dict, req_content: str = "", ref_content: str = "") -> str:
        return await _chat_async(
            "gen_inspection",
            spec_name=inputs.get("spec_name", ""),
            spec_type=inputs.get("spec_type", ""),
            requirements_summary=req_content[:800] if req_content else "（参见§6）",
            reference_inspection=ref_content or "（无参考）",
        )

    async def generate_records(self, inputs: dict) -> str:
        prompt = (
            f"请为规范《{inputs.get('spec_name', '')}》生成\"9 标识与记录\"章节。\n"
            f"格式：9.1 标识要求，9.2 记录与存档（保存期限等）。简洁，不超过150字。"
        )
        llm = get_llm_service()
        return await asyncio.to_thread(
            llm.chat, [{"role": "user", "content": prompt}], max_tokens=300
        )

    # ── 辅助：按章节编号分发重生成 ────────────────────────────────────────────

    async def generate_section_by_number(
        self, section_num: str, inputs: dict, existing_sections: dict
    ) -> str:
        doc_ids = inputs.get("reference_docs", [])
        driver = self._driver

        def _ref(keywords: list[str]) -> str:
            return _retrieve_section_content(driver, doc_ids, keywords)

        mapping: dict[str, Any] = {
            "1": lambda: self.generate_scope(inputs, _ref(["范围", "Scope"])),
            "2": lambda: self.generate_refs(inputs),
            "3": lambda: self.generate_terms(inputs, _ref(["术语", "定义"])),
            "4": lambda: self.generate_materials(inputs),
            "6": lambda: self.generate_requirements(inputs, _ref(["技术要求", "要求"])),
            "7": lambda: self.generate_process(inputs, _ref(["工艺", "规程", "操作"])),
            "8": lambda: self.generate_inspection(
                inputs, existing_sections.get("6", ""), _ref(["检验", "试验"])
            ),
            "9": lambda: self.generate_records(inputs),
        }
        gen_fn = mapping.get(section_num)
        if gen_fn:
            return await gen_fn()
        return f"（章节 {section_num} 暂不支持自动生成）"
