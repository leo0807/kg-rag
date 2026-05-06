"""
基于 synonyms.json 字典 + 图谱 SYNONYM_OF 关系的查询扩展服务
返回 (expanded_query, expansion_info) 二元组
"""
from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from pathlib import Path

from neo4j import Driver

logger = logging.getLogger(__name__)

_STOP_WORDS = {"什么", "要求", "规定", "如何", "怎么", "哪些", "工艺", "标准", "规范"}
_SYNONYMS_FILE = Path(__file__).resolve().parents[2] / "data" / "synonyms.json"


@lru_cache(maxsize=1)
def _load_file_synonyms() -> dict[str, list[str]]:
    try:
        return json.loads(_SYNONYMS_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("synonyms.json 加载失败: %s", exc)
        return {}


def reload_synonyms() -> None:
    """Admin API 写文件后调用此函数使缓存失效。"""
    _load_file_synonyms.cache_clear()


def expand_query(driver: Driver, question: str) -> tuple[str, list[str]]:
    """
    对查询语句进行近义词扩展。

    返回:
        expanded_query: 用于 ES/Neo4j 全文检索的扩展查询字符串
        expansion_info: 人类可读的扩展说明，如 ["钛合金 → TC4, Ti-6Al-4V"]
    """
    potential_terms = re.findall(r'[一-龥]{2,}|[a-zA-Z0-9\-]{2,}', question)
    terms = [t for t in potential_terms if t not in _STOP_WORDS]
    if not terms:
        return question, []

    # ── 文件字典 ──────────────────────────────────────────────────────────────
    file_syns = _load_file_synonyms()
    expanded_map: dict[str, set[str]] = {}
    for t in terms:
        syns = file_syns.get(t)
        if syns:
            expanded_map[t] = set(syns)

    # ── Neo4j SYNONYM_OF ──────────────────────────────────────────────────────
    try:
        with driver.session() as session:
            result = session.run("""
                UNWIND $terms AS term
                MATCH (e {name: term})-[:SYNONYM_OF]-(syn)
                RETURN term, collect(DISTINCT syn.name) AS synonyms
            """, terms=terms)
            for r in result:
                existing = expanded_map.get(r["term"], set())
                expanded_map[r["term"]] = existing | set(r["synonyms"])
    except Exception as exc:
        logger.warning("Neo4j 近义词查询失败: %s", exc)

    if not expanded_map:
        return question, []

    # ── 构造扩展查询 ──────────────────────────────────────────────────────────
    final_query = question
    expansion_info: list[str] = []
    for term, syns in expanded_map.items():
        if not syns:
            continue
        syn_list = [term] + sorted(syns)
        expansion = "(" + " OR ".join(syn_list) + ")"
        new_query = re.sub(rf'\b{re.escape(term)}\b', expansion, final_query)
        if new_query == final_query:
            new_query = final_query.replace(term, expansion)
        if new_query != final_query:
            final_query = new_query
            expansion_info.append(f"{term} → {', '.join(sorted(syns))}")

    logger.info("查询扩展: '%s' -> '%s'", question[:40], final_query[:60])
    return final_query, expansion_info
