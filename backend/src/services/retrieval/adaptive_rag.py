"""
Adaptive RAG — automatic strategy routing based on question classification.

Five question types → five strategies:
  factual      → parallel
  procedural   → sequential + graph
  comparative  → compare
  constraint   → entity-aware
  hypothetical → counterfactual
"""
from __future__ import annotations

import logging
import re
from typing import Literal

from ...core.config import settings
from ..ai.llm_service import get_llm_service

log = logging.getLogger(__name__)

QuestionType = Literal[
    "factual", "procedural", "comparative", "constraint", "hypothetical"
]

STRATEGY_MAP: dict[QuestionType, str] = {
    "factual": "parallel",
    "procedural": "sequential",
    "comparative": "compare",
    "constraint": "graph_augmented",
    "hypothetical": "counterfactual",
}

# Keyword heuristics (fast path before LLM classification)
_PROCEDURAL_PATTERNS = re.compile(
    r"如何|步骤|流程|操作|安装|拆卸|连接|检验|程序|顺序|how to|procedure|steps", re.I
)
_COMPARATIVE_PATTERNS = re.compile(
    r"对比|比较|区别|不同|差异|compare|difference|versus|vs\.", re.I
)
_CONSTRAINT_PATTERNS = re.compile(
    r"力矩|扭矩|压力|温度|公差|上限|下限|规范值|参数|限值|torque|pressure|tolerance", re.I
)
_HYPOTHETICAL_PATTERNS = re.compile(
    r"如果|假设|假如|若|if|what if|would|should.*remove|去掉|省略", re.I
)


def classify_by_heuristic(question: str) -> QuestionType | None:
    """Fast keyword-based classification — avoids LLM call for obvious cases."""
    if _COMPARATIVE_PATTERNS.search(question):
        return "comparative"
    if _PROCEDURAL_PATTERNS.search(question):
        return "procedural"
    if _CONSTRAINT_PATTERNS.search(question):
        return "constraint"
    if _HYPOTHETICAL_PATTERNS.search(question):
        return "hypothetical"
    return None


def classify_by_llm(question: str) -> QuestionType:
    """Use LLM to classify ambiguous questions."""
    try:
        svc = get_llm_service()
        response = svc.chat(
            [
                {
                    "role": "system",
                    "content": (
                        "Classify the question into one of these types: "
                        "factual, procedural, comparative, constraint, hypothetical.\n"
                        "Reply with only one word from the list above."
                    ),
                },
                {"role": "user", "content": question},
            ],
            max_tokens=10,
            timeout=10,
        )
        qtype = response.strip().lower()
        if qtype in STRATEGY_MAP:
            return qtype  # type: ignore[return-value]
    except Exception as exc:
        log.debug("LLM classification failed: %s", exc)
    return "factual"


def classify_question(question: str) -> QuestionType:
    """Classify question type — heuristic first, LLM fallback."""
    heuristic = classify_by_heuristic(question)
    if heuristic:
        return heuristic
    return classify_by_llm(question)


def get_adaptive_strategy(question: str) -> tuple[str, QuestionType]:
    """
    Return (strategy_name, question_type) for a question.
    Strategy name is compatible with existing retrieval router.
    """
    qtype = classify_question(question)
    strategy = STRATEGY_MAP[qtype]
    log.info("Adaptive RAG: question_type=%s → strategy=%s", qtype, strategy)
    return strategy, qtype
