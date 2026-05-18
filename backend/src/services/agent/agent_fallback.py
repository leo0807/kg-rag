from __future__ import annotations

import logging

from ..retrieval.multi_hop_support import fallback_parallel_answer

logger = logging.getLogger(__name__)


async def parallel_rrf_fallback(question: str, tools, top_k: int = 5) -> dict:
    driver = getattr(tools, 'driver', None)
    if driver is None:
        logger.warning('[agent] fallback 失败：tools 未提供 driver')
        return {
            'answer': '在知识库中未找到相关章节，请确认文件已入库。',
            'sources': [],
            'images': [],
            'iterations': 1,
            'strategy_used': 'parallel_rrf_fallback',
            'agent_steps': [],
        }

    answer, sources, steps = fallback_parallel_answer(question, driver, top_k=top_k)
    return {
        'answer': answer,
        'sources': sources,
        'images': [],
        'iterations': 1,
        'strategy_used': 'parallel_rrf_fallback',
        'agent_steps': steps,
    }
