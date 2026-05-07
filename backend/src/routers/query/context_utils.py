from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path


_STOP_WORDS = {"什么", "哪些", "如何", "怎么", "请问", "是否", "问题", "要求"}
_SYNONYM_PATH = Path(__file__).resolve().parents[2] / "data" / "synonyms.json"
_INTENT_RULES = {
    "definition": {
        "markers": ("特性", "性质", "特点", "特征", "定义", "是什么", "有哪些", "基本上都具有"),
        "anchors": ("定义", "术语", "基本要求", "基本特性", "性质", "特性", "特征", "性能"),
        "query_terms": ("定义", "术语", "基本要求", "基本特性", "特性", "性质", "特征"),
    },
    "composition": {
        "markers": ("组成", "构成", "成分", "材料", "配方", "结构"),
        "anchors": ("组成", "构成", "成分", "材料", "配方", "结构"),
        "query_terms": ("组成", "构成", "成分", "材料"),
    },
    "procedure": {
        "markers": ("步骤", "流程", "过程", "方法", "如何", "怎么", "实施", "操作", "执行"),
        "anchors": ("步骤", "流程", "过程", "方法", "操作", "实施", "顺序"),
        "query_terms": ("步骤", "流程", "过程", "方法"),
    },
    "parameter": {
        "markers": ("参数", "压力", "温度", "时间", "范围", "条件", "公差", "数值"),
        "anchors": ("参数", "要求", "范围", "条件", "数值", "公差"),
        "query_terms": ("参数", "要求", "范围", "条件"),
    },
}


@lru_cache(maxsize=1)
def _load_synonym_groups() -> dict[str, tuple[str, ...]]:
    if not _SYNONYM_PATH.exists():
        return {}
    try:
        raw = json.loads(_SYNONYM_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    groups: dict[str, tuple[str, ...]] = {}
    for canonical, aliases in raw.items():
        terms = [canonical]
        terms.extend(alias for alias in aliases if alias)
        groups[canonical] = tuple(dict.fromkeys(terms))
    return groups


def _detect_intent(question: str) -> str:
    q = question or ""
    for intent in ("definition", "procedure", "parameter", "composition"):
        if any(marker in q for marker in _INTENT_RULES[intent]["markers"]):
            return intent
    return "general"


def _build_keyword_list(question: str) -> list[str]:
    q = question or ""
    keywords: list[str] = []
    for term in re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9\.\-]+", q):
        if term in _STOP_WORDS or term in keywords:
            continue
        keywords.append(term)
    for canonical, terms in _load_synonym_groups().items():
        if any(term in q for term in terms):
            for term in terms:
                if term not in keywords:
                    keywords.append(term)
    intent = _detect_intent(q)
    if intent != "general":
        for term in _INTENT_RULES[intent]["query_terms"]:
            if term not in keywords:
                keywords.append(term)
    return keywords


def extract_keywords(question: str) -> list[str]:
    return _build_keyword_list(question)


def _matched_synonym_groups(question: str) -> list[tuple[str, ...]]:
    q = question or ""
    groups = []
    for terms in _load_synonym_groups().values():
        if any(term in q for term in terms):
            groups.append(terms)
    return groups


def _score_source(source: dict, question: str, keywords: list[str]) -> tuple[int, int, int, int]:
    content = source.get("content", "") or ""
    title = source.get("title", "") or ""
    prefix = content[:240]
    intent = _detect_intent(question)
    rules = _INTENT_RULES.get(intent, {"anchors": (), "query_terms": ()})
    anchors = rules.get("anchors", ())
    combined = f"{title}\n{prefix}\n{content}".lower()
    score = 0
    for kw in keywords:
        if kw in title:
            score += 4
        if kw in prefix:
            score += 3
        if kw in content:
            score += 1
    if anchors:
        if any(anchor in title for anchor in anchors):
            score += 5
        if any(anchor in prefix for anchor in anchors):
            score += 3
        if any(anchor in content for anchor in anchors):
            score += 1
    if intent == "definition":
        if any(token in prefix for token in ("定义为", "是指", "包括", "具有", "主要", "一般", "应具有")):
            score += 2
    elif intent == "composition":
        if any(token in prefix for token in ("由", "组成", "构成", "包括")):
            score += 2
    elif intent == "procedure":
        if any(token in prefix for token in ("步骤", "流程", "依次", "先", "后", "顺序")):
            score += 2
    elif intent == "parameter":
        if re.search(r"\d", prefix):
            score += 1
    matched_group_count = 0
    for group in _matched_synonym_groups(question):
        if any(term and term in combined for term in group):
            matched_group_count += 1
            score += 4
    if matched_group_count >= 2:
        score += 4 * matched_group_count
    number = source.get("number") or ""
    depth = -len(number.split(".")) if number else 0
    length = -len(content)
    return score, depth, length, 0


def reorder_sources_for_llm(sources: list[dict], question: str) -> list[dict]:
    keywords = extract_keywords(question)
    return sorted(sources, key=lambda source: _score_source(source, question, keywords), reverse=True)


def build_llm_context(sources: list[dict]) -> str:
    parts = []
    for section in sources:
        parts.append(
            f"[{section['doc_id']} §{section.get('number') or ''}] {section.get('title') or ''}\n{section.get('content') or ''}"
        )
    return "\n\n".join(parts)


def _build_es_query(question: str, keywords: list[str]) -> str:
    intent = _detect_intent(question)
    terms = []
    for canonical, group in _load_synonym_groups().items():
        if any(term in (question or "") for term in group):
            if canonical not in terms:
                terms.append(canonical)
            for alias in group:
                if re.search(r"[A-Za-z]", alias) and alias not in terms:
                    terms.append(alias)
    query_terms = [term for term in keywords if len(term) <= 8 or re.search(r"[A-Za-z0-9\.\-]", term)]
    if not query_terms:
        query_terms = keywords
    for term in query_terms[:4]:
        if term not in terms:
            terms.append(term)
    if intent != "general":
        for term in _INTENT_RULES[intent]["query_terms"][:4]:
            if term not in terms:
                terms.append(term)
    return " ".join(term for term in terms if term)


def augment_feature_definition_sources(sources: list[dict], question: str) -> list[dict]:
    intent = _detect_intent(question)
    if intent == "general":
        return sources
    try:
        from ...services.storage.es_store import search_sections_es
    except Exception:
        return sources

    keywords = extract_keywords(question)
    probe_queries = []
    for canonical, group in _load_synonym_groups().items():
        if any(term in (question or "") for term in group):
            english_alias = next((alias for alias in group if re.search(r"[A-Za-z]", alias)), "")
            probe_queries.append(english_alias or canonical)
    extra_query = _build_es_query(question, keywords)
    if extra_query.strip():
        probe_queries.insert(0, extra_query)
    probe_queries = [q for i, q in enumerate(probe_queries) if q and q not in probe_queries[:i]]
    if not probe_queries:
        return sources

    existing = {s.get("chunk_id") for s in sources}
    ranked_candidates = []
    for probe in probe_queries[:4]:
        try:
            candidates = search_sections_es(probe, top_k=5)
        except Exception:
            continue
        for cand in candidates:
            if cand.get("chunk_id") in existing:
                continue
            cand_score = _score_source(cand, question, keywords)
            if cand_score[0] > 0:
                cand["score"] = max(float(cand.get("score") or 0.0), 100.0 + cand_score[0])
                ranked_candidates.append((cand_score, cand))
    if ranked_candidates:
        ranked_candidates.sort(key=lambda item: item[0], reverse=True)
        for _score, cand in ranked_candidates[:3]:
            if cand.get("chunk_id") not in existing:
                sources.append(cand)
                existing.add(cand.get("chunk_id"))
    return sources
