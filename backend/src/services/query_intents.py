from __future__ import annotations

from typing import TYPE_CHECKING
import re

from .answer_humanizer import humanize_answer_text

if TYPE_CHECKING:
    from neo4j import Driver

_COUNT_WORDS = ("多少", "几本", "总共", "一共", "共有", "总数", "数量")
_CPS_WORD_RE = re.compile(r"(?i)\bCPS\b|CPS")


def is_total_cps_count_question(question: str | None) -> bool:
    q = (question or "").strip()
    if not q:
        return False
    if not _CPS_WORD_RE.search(q):
        return False
    return any(word in q for word in _COUNT_WORDS)


def build_total_cps_count_answer(count: int) -> str:
    return humanize_answer_text(f"系统里共有 {count} 本 CPS 文档。")


def get_total_cps_count(driver: Driver) -> int:
    with driver.session() as session:
        record = session.run(
            "MATCH (d:Document) WHERE d.title IS NOT NULL RETURN count(d) AS cnt"
        ).single()
    return int(record["cnt"] if record and record["cnt"] is not None else 0)
