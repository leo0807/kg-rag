from __future__ import annotations

import re
import logging
import pdfplumber
from pathlib import Path

from .parser_patterns import _NON_TITLE, _BLACKLIST_RE

logger = logging.getLogger(__name__)


def clean_content(text: str) -> str:
    text = re.sub(
        r'专有信息声明.*?有限责任公司保留本文件一切版权。',
        '', text, flags=re.DOTALL
    )
    text = re.sub(r'CPS\d+版\s*本:\s*[A-Z]\s*第\d+页\s*共\d+页', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text).strip()
    return clean_ocr_artifacts(text)


def clean_ocr_artifacts(text: str) -> str:
    if not text:
        return text

    # 修复常见 OCR 错误
    # 'D' 被误识别为小数点（如 0D6 → 0.6）
    text = re.sub(r'(\d)D(\d)', r'\1.\2', text)

    # 'is' 被误识别为 '0'
    text = re.sub(r'\bis\b(?=\d)', '0', text)
    text = re.sub(r'(?<=\d)\bis\b', '0', text)

    # 连续的 'is' 替换为对应数字
    text = re.sub(r'isis', '00', text)

    # 修复单位前的空格
    text = re.sub(r'(\d)\s*(MPa|kPa|℃|mm|min|kg)\b', r'\1 \2', text)

    return text


def extract_refs(sections: list[dict]) -> list[str]:
    for section in sections:
        if section["number"] == "2":
            refs = re.findall(r"\b(C[PD]S\d+)\b", section["content"])
            return list(set(refs))
    return []


def _is_blacklisted(text: str) -> bool:
    t = text.strip()
    return any(rx.search(t) for rx in _BLACKLIST_RE)


def _extract_title_fallback(cover_text: str, pdf_path: Path) -> str:
    fn_match = re.search(
        r'CPS\d+_[A-Z]_([\u4e00-\u9fff\w\-·]+?)_\d+\.pdf',
        pdf_path.name, re.IGNORECASE,
    )
    if fn_match:
        candidate = fn_match.group(1).strip()
        if len(candidate) >= 4:
            return candidate

    lines = [l.strip() for l in cover_text.split('\n') if l.strip()]
    for line in lines:
        if len(line) < 4:
            continue
        if _NON_TITLE.match(line):
            continue
        if not re.search(r'[\u4e00-\u9fff]', line):
            continue
        return line

    return lines[1] if len(lines) > 1 else ""


def extract_title_from_first_page(pdf_path: Path) -> str:
    try:
        with pdfplumber.open(pdf_path) as pdf:
            words = pdf.pages[0].extract_words(extra_attrs=["fontname", "size"])
    except Exception:
        return ""

    clean_words = [
        w for w in words
        if w.get("size") and w["size"] > 0 and not _is_blacklisted(w["text"])
    ]
    if not clean_words:
        return ""

    max_size = max(w["size"] for w in clean_words)
    title_words = [w for w in clean_words if abs(w["size"] - max_size) <= 0.5]
    title_words.sort(key=lambda w: (round(w["top"]), w["x0"]))

    lines: list[list[str]] = []
    current_row: int | None = None
    for w in title_words:
        row = round(w["top"])
        if current_row is None or abs(row - current_row) > 2:
            lines.append([w["text"]])
            current_row = row
        else:
            lines[-1].append(w["text"])

    title = " ".join("".join(line) for line in lines).strip()
    return title


def extract_meta(pdf_path: Path) -> dict:
    with pdfplumber.open(pdf_path) as pdf:
        cover_text = pdf.pages[0].extract_text() or ""

    doc_match = re.search(r'(CPS\d+)\s*版本[:：]\s*([A-Z])', cover_text)
    if not doc_match:
        name_match = re.search(r'(CPS\d+)', pdf_path.stem)
        doc_id  = name_match.group(1) if name_match else ""
        version = ""
    else:
        doc_id  = doc_match.group(1)
        version = doc_match.group(2)

    title = extract_title_from_first_page(pdf_path)

    if not title:
        title_match = re.search(
            r'中国商用飞机有限责任公司(?:规范|文件)\n(.*?)\n',
            cover_text
        )
        if title_match:
            title = title_match.group(1).strip()

    if not title:
        title = _extract_title_fallback(cover_text, pdf_path)

    date_match = re.search(r'(\d{4}-\d{2}-\d{2})', cover_text)
    issue_date = date_match.group(1) if date_match else ""

    return {"doc_id": doc_id, "version": version, "title": title, "issue_date": issue_date}
