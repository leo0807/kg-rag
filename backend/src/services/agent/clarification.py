from __future__ import annotations

import asyncio
import json
import logging
import re
from collections import OrderedDict

from ...core.config import settings
from ...services.ai.llm_service import get_llm_service

logger = logging.getLogger(__name__)


class ClarificationDetector:
    """判定问题是否需要主动澄清。"""

    VAGUE_PATTERNS = [
        r"^密封怎么做",
        r"^如何安装",
        r"^工艺要求是什么",
        r"^规范要求",
        r"^怎么处理",
    ]

    def __init__(
        self,
        llm_service=None,
        enabled: bool | None = None,
        min_question_length: int | None = None,
        use_llm_check: bool | None = None,
    ) -> None:
        self.llm = llm_service or get_llm_service()
        self.enabled = settings.CLARIFICATION_ENABLED if enabled is None else enabled
        self.min_question_length = (
            settings.CLARIFICATION_MIN_LENGTH
            if min_question_length is None
            else min_question_length
        )
        self.use_llm_check = (
            settings.CLARIFICATION_LLM_CHECK
            if use_llm_check is None
            else use_llm_check
        )

    async def needs_clarification(
        self,
        question: str,
        driver,
        skip: bool = False,
    ) -> dict:
        question = (question or "").strip()
        if not self.enabled:
            return {"needs_clarification": False}
        if skip:
            return {"needs_clarification": False}
        if "具体关于" in question or re.search(r"CPS\d+", question):
            return {"needs_clarification": False}

        if len(question) < self.min_question_length:
            return {
                "needs_clarification": True,
                "reason": "问题过于简短",
                "clarification_options": await self._generate_options(question, driver),
            }

        for pattern in self.VAGUE_PATTERNS:
            if re.match(pattern, question):
                return {
                    "needs_clarification": True,
                    "reason": "问题范围过广",
                    "clarification_options": await self._generate_options(question, driver),
                }

        has_cps_ref = bool(re.search(r"CPS\d+", question))
        if not has_cps_ref and self.use_llm_check:
            ambiguity = await self._llm_check_ambiguity(question)
            if ambiguity.get("is_ambiguous"):
                return {
                    "needs_clarification": True,
                    "reason": ambiguity.get("reason", "问题存在歧义"),
                    "clarification_options": await self._generate_options(question, driver),
                }

        return {"needs_clarification": False}

    async def _generate_options(self, question: str, driver) -> list[str]:
        keywords = self._extract_keywords(question)
        if not keywords:
            keywords = [question[:10]] if question else []

        options: list[str] = []
        seen: set[str] = set()

        def _query() -> list[dict]:
            rows: list[dict] = []
            with driver.session() as session:
                for kw in keywords[:3]:
                    result = session.run(
                        """
                        MATCH (d:Document)-[:HAS_SECTION]->(sec:Section)
                        WHERE toLower(sec.title) CONTAINS toLower($kw)
                           OR toLower(sec.content) CONTAINS toLower($kw)
                        RETURN DISTINCT d.doc_id AS doc_id,
                                        coalesce(d.title, d.name, d.doc_id) AS title
                        LIMIT 5
                        """,
                        kw=kw[:10],
                    )
                    rows.extend(dict(r) for r in result)
            return rows

        try:
            results = await asyncio.to_thread(_query)
        except Exception as exc:
            logger.debug("澄清选项查询失败: %s", exc)
            results = []

        for row in results:
            doc_id = str(row.get("doc_id") or "").strip()
            if not doc_id or doc_id in seen:
                continue
            seen.add(doc_id)
            title = str(row.get("title") or doc_id).strip()
            options.append(f"{doc_id}：{title}")
            if len(options) >= 4:
                break

        if options:
            return options

        return [
            "密封圈安装工艺（CPS7251）",
            "燃油箱密封工艺（CPS1000）",
            "导管接头密封（CPS1328）",
            "其他密封相关工艺",
        ]

    async def _llm_check_ambiguity(self, question: str) -> dict:
        prompt = f"""判断以下航空工艺问题是否模糊：
问题：{question}

如果问题涉及多个可能的规范或工艺领域，返回：
{{"is_ambiguous": true, "reason": "原因"}}

如果问题足够具体，返回：
{{"is_ambiguous": false}}

只返回JSON。"""
        try:
            response = await asyncio.to_thread(
                self.llm.chat,
                [{"role": "user", "content": prompt}],
                "",
                max_tokens=100,
            )
            if not response:
                return {"is_ambiguous": False}
            m = re.search(r"\{.*\}", response, re.DOTALL)
            if not m:
                return {"is_ambiguous": False}
            parsed = json.loads(m.group())
            if isinstance(parsed, dict):
                return parsed
        except Exception as exc:
            logger.debug("澄清模糊度 LLM 检测失败: %s", exc)
        return {"is_ambiguous": False}

    @staticmethod
    def _extract_keywords(question: str) -> list[str]:
        tokens = re.findall(r"CPS\d+|[A-Za-z]{3,}|[\u4e00-\u9fff]{2,6}", question or "")
        stop_words = {
            "如何",
            "怎么",
            "怎样",
            "什么",
            "请问",
            "一下",
            "问题",
            "要求",
            "规范",
            "请",
            "问",
        }
        ordered = OrderedDict()
        for token in tokens:
            token = token.strip()
            if len(token) < 2 or token in stop_words:
                continue
            ordered[token] = None
        return list(ordered.keys())
