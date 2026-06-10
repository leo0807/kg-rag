"""F4.2 — Content moderation: keyword-based + length checks."""
from __future__ import annotations

import re

# Expandable lists; in production replace with ML model or external API
_SENSITIVE_PATTERNS = [
    re.compile(r"\b(password|passwd|密码|secret|token|api[_\s]?key)\b", re.I),
    re.compile(r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b"),  # credit card pattern
    re.compile(r"\b1[3-9]\d{9}\b"),  # CN mobile
]

_BLOCKED_KEYWORDS = {"fuck", "shit", "涉密", "绝密", "机密"}

MAX_CONTENT_LENGTH = 50_000


def moderate(content: str) -> dict:
    """
    Returns:
        {"ok": True} if content passes,
        {"ok": False, "reason": str} otherwise.
    """
    if len(content) > MAX_CONTENT_LENGTH:
        return {"ok": False, "reason": f"内容超过最大长度 {MAX_CONTENT_LENGTH} 字符"}

    lower = content.lower()
    for kw in _BLOCKED_KEYWORDS:
        if kw in lower:
            return {"ok": False, "reason": f"包含受限关键词: {kw}"}

    for pat in _SENSITIVE_PATTERNS:
        m = pat.search(content)
        if m:
            return {"ok": False, "reason": f"检测到敏感信息模式: {m.group()[:20]}"}

    return {"ok": True}
