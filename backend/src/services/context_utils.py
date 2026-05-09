from __future__ import annotations

from typing import Any

MAX_HISTORY_ROUNDS = 3


def trim_conversation_history(history: list[dict[str, Any]] | None, max_rounds: int = MAX_HISTORY_ROUNDS) -> list[dict[str, str]]:
    if not history:
        return []
    recent = history[-max(0, max_rounds) * 2:]
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
