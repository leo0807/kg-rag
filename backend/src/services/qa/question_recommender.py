"""
智能提问建议 — 基于当前答案用 LLM 生成延伸问题
"""
from __future__ import annotations

import json
import logging
import re

from ...services.ai.llm_service import get_llm_service

logger = logging.getLogger(__name__)

_PROMPT_TMPL = """你是一个航空工艺规范领域的助手。
根据用户刚才的问答，生成 3-5 个有价值的延伸问题。

要求：
- 与当前主题相关，但角度不同
- 都是工艺规范领域的专业问题
- 简洁明了，不超过 30 字
- 不重复当前问题

当前问题：{question}
当前答案摘要：{answer_summary}

只输出 JSON，格式如下（不要有任何其他文字）：
{{"questions": ["问题1", "问题2", "问题3"]}}"""


class QuestionRecommender:
    def __init__(self):
        self._llm = None

    @property
    def llm(self):
        if self._llm is None:
            self._llm = get_llm_service()
        return self._llm

    async def recommend(
        self,
        question: str,
        answer: str,
        conversation_history: list[dict] | None = None,
    ) -> list[str]:
        """生成延伸问题，失败时静默返回空列表。"""
        if not question or not answer:
            return []
        try:
            return await self._generate(question, answer)
        except Exception as e:
            logger.debug("recommend failed: %s", e)
            return []

    async def _generate(self, question: str, answer: str) -> list[str]:
        import asyncio
        prompt = _PROMPT_TMPL.format(
            question=question[:200],
            answer_summary=answer[:500],
        )
        raw = await asyncio.to_thread(
            self.llm.chat,
            [{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.7,
        )
        return _parse_questions(raw)


def _parse_questions(raw: str) -> list[str]:
    """从 LLM 输出中提取问题列表，兼容 JSON 和纯文本。"""
    if not raw:
        return []
    # try JSON first
    try:
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if m:
            data = json.loads(m.group())
            qs = data.get("questions", [])
            if isinstance(qs, list):
                return [str(q).strip() for q in qs if str(q).strip()][:5]
    except Exception:
        pass
    # fallback: line-by-line
    lines = [l.strip().lstrip("•·-–—1234567890.）)") .strip() for l in raw.splitlines()]
    return [l for l in lines if 5 < len(l) <= 60][:5]


# module-level singleton
_recommender: QuestionRecommender | None = None

def get_recommender() -> QuestionRecommender:
    global _recommender
    if _recommender is None:
        _recommender = QuestionRecommender()
    return _recommender
