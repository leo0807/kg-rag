from __future__ import annotations

import re

_LEADING_BOILERPLATE_RE = re.compile(
    r"^(根据(提供的|检索到的|当前检索结果|以上)?(规范内容|内容|结果)?[，,：:]\s*)+"
)
_CLOSING_BOILERPLATE_RE = re.compile(
    r"(?:\s*(?:综上所述|总的来说|简单来说|简单说|整体来看)[，,：:]\s*)+$"
)
_MULTI_SPACE_RE = re.compile(r"[ \t]{2,}")
_MULTI_NEWLINE_RE = re.compile(r"\n{3,}")
_BULLET_RE = re.compile(r"(?<!\n)([-•]\s+)")
_ENUM_RE = re.compile(r"(?<!\n)(\d{1,3}\.\s*)(?=[^\d])")
_PUNCT_SPLIT_RE = re.compile(r"([。！？；;])\s*(?=[^\s\]】）)」』])")
_HEADING_RE = re.compile(r"(?m)^(#{1,6})(\S)")

_PHRASE_REPLACEMENTS = (
    ("根据提供的规范内容，", ""),
    ("根据检索到的规范，", ""),
    ("根据当前检索结果，", ""),
    ("根据提供的内容，", ""),
    ("可以看出，", ""),
    ("从检索结果来看，", ""),
    ("从当前检索结果来看，", ""),
    ("总体上，", "简单说，"),
    ("总的来说，", "简单说，"),
    ("综上所述，", "简单说，"),
)


def humanize_answer_text(text: str | None, question: str | None = None) -> str:
    del question
    if not text:
        return ""

    value = str(text).replace("\ufffd", "").replace("\u00A0", " ").strip()
    for old, new in _PHRASE_REPLACEMENTS:
        value = value.replace(old, new)

    value = _LEADING_BOILERPLATE_RE.sub("", value)
    value = _CLOSING_BOILERPLATE_RE.sub("", value).strip()
    value = _HEADING_RE.sub(r"\1 \2", value)

    lines: list[str] = []
    for raw_line in value.splitlines():
        line = raw_line.strip()
        if not line:
            lines.append("")
            continue
        if line.startswith(("### ", "## ", "# ", "- ", "• ", "* ")):
            lines.append(line)
            continue
        if re.match(r"^\d{1,3}\.\s*", line):
            lines.append(line)
            continue
        line = _MULTI_SPACE_RE.sub(" ", line)
        line = _ENUM_RE.sub(r"\n\1", line)
        line = _BULLET_RE.sub(r"\n\1", line)
        line = _PUNCT_SPLIT_RE.sub(r"\1\n", line)
        parts = [part.strip() for part in line.split("\n") if part.strip()]
        lines.extend(parts or [line])

    value = "\n".join(lines)
    value = _MULTI_NEWLINE_RE.sub("\n\n", value)
    value = re.sub(r"([，,。！？；;：:])\1+", r"\1", value)
    value = re.sub(r"^\s*[，,。；;：:、\-\s]+", "", value)
    return value.strip()
