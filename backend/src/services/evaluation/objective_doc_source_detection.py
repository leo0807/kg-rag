from __future__ import annotations

import re
from typing import Any

_CPS_RE = re.compile(r"CPS\d{4}", re.IGNORECASE)


def _normalize_source_doc_id(value: str | None) -> str:
    return (value or "").strip().upper()


def detect_source_doc(filename: str, questions: list[dict[str, Any]]) -> str:
    if filename:
        match = _CPS_RE.search(filename)
        if match:
            return match.group(0).upper()

    counts: dict[str, int] = {}
    for question in questions[:20]:
        text_bits: list[str] = [
            str(question.get("doc_id", "") or ""),
            str(question.get("question", "") or ""),
            str(question.get("stem", "") or ""),
        ]
        options = question.get("options") or []
        if isinstance(options, list):
            for option in options:
                if isinstance(option, dict):
                    text_bits.append(str(option.get("text", "") or ""))
                else:
                    text_bits.append(str(option))
        text = " ".join(bit for bit in text_bits if bit)
        for cps in _CPS_RE.findall(text):
            normalized = cps.upper()
            counts[normalized] = counts.get(normalized, 0) + 1

    if counts:
        return max(counts, key=counts.get)
    return ""


def resolve_source_doc_id(
    filename: str,
    questions: list[dict[str, Any]],
    source_doc_id: str = "",
    legacy_doc_id: str = "",
) -> str:
    explicit = _normalize_source_doc_id(source_doc_id) or _normalize_source_doc_id(legacy_doc_id)
    if explicit:
        return explicit
    return detect_source_doc(filename, questions)


def baseline_retrieval_hit_rate(
    questions: list[dict[str, Any]],
    source_doc_id: str,
    strategy: str,
    top_k: int,
    driver,
) -> tuple[float, list[dict[str, Any]]]:
    if not source_doc_id or not questions:
        return 1.0, []

    from .objective_doc_eval_runner import retrieve_objective_sections

    samples = questions[:3]
    details: list[dict[str, Any]] = []
    hit_count = 0
    for question in samples:
        stem = str(question.get("question") or question.get("stem") or "")
        options = question.get("options") or []
        sections, _ = retrieve_objective_sections(
            stem,
            options,
            strategy,
            top_k,
            driver,
            doc_id=source_doc_id,
        )
        section_doc_ids = sorted(
            {
                str(section.get("doc_id", "")).upper()
                for section in sections
                if section.get("doc_id")
            }
        )
        hit = source_doc_id.upper() in section_doc_ids
        if hit:
            hit_count += 1
        details.append(
            {
                "question": stem[:120],
                "hit": hit,
                "doc_ids": section_doc_ids[:8],
            }
        )

    return hit_count / max(len(samples), 1), details
