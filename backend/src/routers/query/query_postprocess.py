from __future__ import annotations

import re


def _boost_query_relevant_sections(
    sections: list[dict],
    question: str,
    expansion_info: list[str],
    use_hyde: bool,
) -> None:
    terms = set(re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9\.\-]+", question))
    for info in expansion_info:
        for term in re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9\.\-]+", info):
            terms.add(term)
    if use_hyde:
        terms.update({"0.6MPa", "-0.08MPa", "真空袋", "真空度", "压力"})

    for section in sections:
        text = f"{section.get('title', '')}\n{section.get('content', '')}"
        hits = sum(1 for term in terms if term and term in text)
        if not hits:
            continue
        bonus = hits * 1.8
        if "0.6MPa" in text or "0.6 MPa" in text:
            bonus += 4.0
        if "-0.08MPa" in text or "-0.08 MPa" in text:
            bonus += 4.0
        if "真空袋" in text and "压力" in text:
            bonus += 2.0
        section["score"] = round((section.get("score") or 0.0) + bonus, 4)
