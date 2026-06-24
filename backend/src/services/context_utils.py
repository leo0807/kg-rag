from __future__ import annotations

import re
from typing import Any

MAX_HISTORY_ROUNDS = 3
_CPS_RE = re.compile(r"(?<![A-Z0-9])CPS\d{3,4}(?![A-Z0-9])", re.IGNORECASE)


def trim_conversation_history(history: list[dict[str, Any]] | None, max_rounds: int = MAX_HISTORY_ROUNDS) -> list[dict[str, str]]:
    if not history:
        return []
    if max_rounds <= 0:
        return []
    recent = history[-max_rounds * 2:]
    cleaned: list[dict[str, str]] = []
    for item in recent:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "user"))
        if role == "system":
            continue
        content = str(item.get("content", "") or "").strip()
        if not content:
            continue
        cleaned.append({"role": role, "content": content})
    return cleaned


def trim_conversation_history_for_question(
    question: str | None,
    history: list[dict[str, Any]] | None,
    max_rounds: int = MAX_HISTORY_ROUNDS,
) -> list[dict[str, str]]:
    if _CPS_RE.search(question or ""):
        return []
    return trim_conversation_history(history, max_rounds=max_rounds)


def extract_question_doc_ids(question: str | None) -> list[str]:
    if not question:
        return []
    return list(dict.fromkeys(match.upper() for match in _CPS_RE.findall(question)))


def normalize_doc_hints(doc_hints: list[str] | None) -> list[str]:
    if not doc_hints:
        return []
    return list(dict.fromkeys(str(doc_id).strip().upper() for doc_id in doc_hints if str(doc_id).strip()))


def resolve_retrieval_doc_id(question: str | None, doc_hints: list[str] | None = None) -> str:
    doc_ids = extract_question_doc_ids(question)
    if len(doc_ids) == 1:
        return doc_ids[0]
    hint_ids = normalize_doc_hints(doc_hints)
    return hint_ids[0] if len(hint_ids) == 1 else ""
