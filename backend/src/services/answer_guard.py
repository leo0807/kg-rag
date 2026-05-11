from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

_CPS_RE = re.compile(r"(?<![A-Z0-9])CPS\d{3,4}(?![A-Z0-9])", re.IGNORECASE)
_CPS_NOISY_RE = re.compile(r"(?i)(?<![A-Z0-9])CPS[a-z0-9._\-]{1,12}")
_COMPARE_HINT_RE = re.compile(r"(不同|差异|区别|比较|对比)")


def _source_doc_ids(sources: list[dict] | None) -> set[str]:
    if not sources:
        return set()
    return {str(s.get("doc_id") or "").strip() for s in sources if str(s.get("doc_id") or "").strip()}


def validate_answer(answer: str | None, sources: list[dict] | None, question: str | None = None) -> str:
    text = (answer or "").strip()
    if not text:
        return ""

    source_refs = _source_doc_ids(sources)
    if not source_refs:
        return text

    question_refs = {ref for ref in _CPS_RE.findall(question or "")}
    if question_refs and (_COMPARE_HINT_RE.search(question or "") or len(question_refs) >= 1):
        source_refs = source_refs & question_refs or question_refs
    question_single_ref = next(iter(question_refs), "") if len(question_refs) == 1 else ""
    source_single_ref = next(iter(source_refs), "") if len(source_refs) == 1 else ""
    primary_ref = question_single_ref or source_single_ref
    if primary_ref and not _COMPARE_HINT_RE.search(question or ""):
        text = _CPS_NOISY_RE.sub(
            lambda match: primary_ref if match.group(0).upper() != primary_ref else match.group(0),
            text,
        )

    answer_refs = set(_CPS_RE.findall(text))
    hallucinated = sorted(answer_refs - source_refs)
    if not hallucinated:
        return text

    logger.warning(
        "发现幻觉规范编号: %s | question=%s | sources=%s",
        hallucinated,
        (question or "")[:120],
        sorted(source_refs),
    )

    def _replace(match: re.Match[str]) -> str:
        token = match.group(0)
        return token if token in source_refs else ""

    text = _CPS_RE.sub(_replace, text)
    text = re.sub(r"\s{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"\s+([,，。；;：:])", r"\1", text)
    text = re.sub(r"([,，。；;：:])\1+", r"\1", text)
    text = re.sub(r"^[和与及,，。；;：:\s]+", "", text)
    text = text.strip()
    if not text:
        text = "根据当前检索结果，未能找到足够信息进行回答，请尝试更具体的问题描述。"
    else:
        text += "\n\n⚠️ 注意：以上答案仅基于已检索到的章节，请以原始规范文档为准。"
    return text
