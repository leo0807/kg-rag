from __future__ import annotations

"""约束冲突与语义冲突检测逻辑"""
import asyncio
import logging
from typing import Any

from neo4j import Driver

logger = logging.getLogger(__name__)

_JUDGE_SYSTEM = (
    "你是一位严谨的航空工艺规范审核专家。"
    "给定来自不同文档的两段工艺规范内容，判断它们对同一主题是否存在矛盾。"
)

_JUDGE_TMPL = """\
## 共同主题
实体：{entity}（类型：{entity_type}）

## 文档 A（{doc_a}）· 章节 {section_a_number}
标题：{section_a_title}
内容：{section_a_content}

## 文档 B（{doc_b}）· 章节 {section_b_number}
标题：{section_b_title}
内容：{section_b_content}

## 判断要求
严格判断两段内容是否对同一操作/参数/材料存在矛盾或不一致定义。
输出严格 JSON（不要多余文字）：
{{
  "has_conflict": true 或 false,
  "severity": "high" 或 "medium" 或 "low",
  "description": "一句话描述冲突内容，没有冲突填空字符串",
  "entity_in_conflict": "冲突聚焦的具体术语或参数名"
}}"""

_CONSTRAINT_CYPHER = """
MATCH (s1:Section)-[:HAS_CONSTRAINT]->(c1:Constraint)
MATCH (s2:Section)-[:HAS_CONSTRAINT]->(c2:Constraint)
WHERE c1.type = c2.type AND c1.unit = c2.unit AND s1.doc_id <> s2.doc_id AND id(c1) < id(c2)
  AND (
    (c1.value <> '' AND c2.value <> '' AND c1.value <> c2.value)
    OR (c1.value_min <> '' AND c2.value_min <> '' AND c1.value_min <> c2.value_min)
    OR (c1.value_max <> '' AND c2.value_max <> '' AND c1.value_max <> c2.value_max)
  )
RETURN
  s1.chunk_id AS chunk_a, s1.doc_id AS doc_a, s1.number AS num_a, s1.title AS title_a,
  substring(s1.content, 0, 400) AS snippet_a,
  s2.chunk_id AS chunk_b, s2.doc_id AS doc_b, s2.number AS num_b, s2.title AS title_b,
  substring(s2.content, 0, 400) AS snippet_b,
  c1.type AS ctype, c1.unit AS unit,
  c1.value AS val_a, c1.value_min AS min_a, c1.value_max AS max_a,
  c2.value AS val_b, c2.value_min AS min_b, c2.value_max AS max_b
LIMIT $limit
"""

_ENTITY_CYPHER = """
MATCH (e)<-[:REQUIRES_TOOL|USES_MATERIAL|INVOLVES_PROCESS]-(s1:Section)
MATCH (e)<-[:REQUIRES_TOOL|USES_MATERIAL|INVOLVES_PROCESS]-(s2:Section)
WHERE s1.doc_id <> s2.doc_id AND id(s1) < id(s2)
WITH labels(e)[0] AS etype, e.name AS ename, s1, s2
RETURN etype, ename,
  s1.chunk_id AS chunk_a, s1.doc_id AS doc_a, s1.number AS num_a, s1.title AS title_a,
  substring(s1.content, 0, 500) AS content_a,
  s2.chunk_id AS chunk_b, s2.doc_id AS doc_b, s2.number AS num_b, s2.title AS title_b,
  substring(s2.content, 0, 500) AS content_b
LIMIT $limit
"""


def _call_llm(messages: list[dict]) -> str:
    from ..ai.service import get_llm_service
    return get_llm_service().chat(messages)


def _parse_verdict(raw: str) -> dict[str, Any]:
    import json, re
    m = re.search(r"\{[\s\S]*\}", raw)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    return {"has_conflict": False, "severity": "low", "description": "", "entity_in_conflict": ""}


def detect_constraint_conflicts(driver: Driver, limit: int = 200) -> list[dict[str, Any]]:
    with driver.session() as session:
        result = session.run(_CONSTRAINT_CYPHER, limit=limit)
        rows = []
        for rec in result:
            r = dict(rec)
            val_a = r["val_a"] or f"{r['min_a']}~{r['max_a']}"
            val_b = r["val_b"] or f"{r['min_b']}~{r['max_b']}"
            rows.append({
                "conflict_type": "constraint", "severity": "high",
                "entity_name": r["ctype"], "entity_type": "Constraint",
                "section_a_chunk_id": r["chunk_a"] or "", "section_a_doc_id": r["doc_a"] or "",
                "section_a_title": r["title_a"] or "", "section_a_snippet": r["snippet_a"] or "",
                "section_b_chunk_id": r["chunk_b"] or "", "section_b_doc_id": r["doc_b"] or "",
                "section_b_title": r["title_b"] or "", "section_b_snippet": r["snippet_b"] or "",
                "description": f"{r['ctype']}（{r['unit']}）：文档A={val_a}，文档B={val_b}",
            })
    return rows


def fetch_entity_pairs(driver: Driver, limit: int = 60) -> list[dict[str, Any]]:
    with driver.session() as session:
        result = session.run(_ENTITY_CYPHER, limit=limit)
        return [dict(r) for r in result]


async def judge_pair(pair: dict[str, Any]) -> dict[str, Any] | None:
    prompt = _JUDGE_TMPL.format(
        entity=pair["ename"], entity_type=pair["etype"],
        doc_a=pair["doc_a"], section_a_number=pair.get("num_a", ""),
        section_a_title=pair.get("title_a", ""), section_a_content=pair.get("content_a", ""),
        doc_b=pair["doc_b"], section_b_number=pair.get("num_b", ""),
        section_b_title=pair.get("title_b", ""), section_b_content=pair.get("content_b", ""),
    )
    messages = [{"role": "system", "content": _JUDGE_SYSTEM}, {"role": "user", "content": prompt}]
    try:
        raw = await asyncio.to_thread(_call_llm, messages)
        verdict = _parse_verdict(raw)
    except Exception as exc:
        logger.warning("LLM 判断失败: %s", exc)
        return None
    if not verdict.get("has_conflict"):
        return None
    return {
        "conflict_type": "semantic",
        "severity": verdict.get("severity", "medium"),
        "entity_name": verdict.get("entity_in_conflict") or pair["ename"],
        "entity_type": pair["etype"],
        "section_a_chunk_id": pair.get("chunk_a", ""), "section_a_doc_id": pair.get("doc_a", ""),
        "section_a_title": pair.get("title_a", ""),
        "section_a_snippet": (pair.get("content_a", "") or "")[:400],
        "section_b_chunk_id": pair.get("chunk_b", ""), "section_b_doc_id": pair.get("doc_b", ""),
        "section_b_title": pair.get("title_b", ""),
        "section_b_snippet": (pair.get("content_b", "") or "")[:400],
        "description": verdict.get("description", ""),
    }
