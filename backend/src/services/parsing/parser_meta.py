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

    # 第一遍单位空格修复（为后面的 D→小数点规则创造词边界，去掉 \b 以兼容非 ASCII 单位符号）
    text = re.sub(r'(\d)\s*(MPa|kPa|℃|mm|min|kg)', r'\1 \2', text)

    # 'D' 被误识别为小数点（如 0D6→0.6，0D017→0.017）
    # 使用 \b 词边界：在零件编号（如 CETR0001D08）中字母与数字相邻，无词边界，不会匹配
    text = re.sub(r'\b(\d+)D(\d+)\b', r'\1.\2', text)

    # ── is / N 误识别清理 ──────────────────────────────────
    # 所有规则都要求"is/N"出现在数字上下文中，避免误伤合法英文文本。

    # 连续 is/N 长序列（≥3）→ 空（"isisN..." 等只在数字段出现）
    text = re.sub(r'(?:is|N){3,}', '', text)

    # 'isis' → '00'（两个连续 is）
    text = re.sub(r'isis', '00', text)

    # 'isN' / 'isn' → '00'（仅在数字附近成立）
    text = re.sub(r'(?<=\d)is[Nn]', '00', text)
    text = re.sub(r'is[Nn](?=\d)', '00', text)

    # 数字后紧跟 is → 0（如 "5is" → "50"）
    text = re.sub(r'(\d)is(?!\w)', r'\g<1>0', text)

    # is 后紧跟数字 → 0+数字（如 "is5" → "05"）
    text = re.sub(r'(?<!\w)is(\d)', r'0\1', text)

    # 数字间夹 N（如 "5N6" → "56"）
    text = re.sub(r'(\d)N(\d)', r'\1\2', text)

    # 重复标点 / 多余空行
    text = re.sub(r'([。，、；：！？])\1+', r'\1', text)
    text = re.sub(r'\n{3,}', '\n\n', text)

    # 第二遍单位空格修复（处理替换后产生的新数字+单位连接）
    text = re.sub(r'(\d)\s*(MPa|kPa|℃|mm|min|kg)', r'\1 \2', text)

    return text.strip()


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
    if re.search(r"(目次|Contents|SHEET\s+\d+\s+OF\s+\d+)", title, re.IGNORECASE):
        return ""
    return title


def extract_meta(pdf_path: Path) -> dict:
    with pdfplumber.open(pdf_path) as pdf:
        cover_text = pdf.pages[0].extract_text() or ""

    doc_match = re.search(r'(CPS\d+)\s*版本[:：]\s*([A-Z])', cover_text)
    if not doc_match:
        name_match = re.search(r'(cps\d+)', pdf_path.stem, re.IGNORECASE)
        doc_id  = name_match.group(1).upper() if name_match else ""
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
    if re.search(r"(目次|Contents|SHEET\s+\d+\s+OF\s+\d+)", title, re.IGNORECASE):
        title = ""
    if title and (re.search(r"\.{8,}", title) or re.search(r"\b\d+\b\s*$", title)):
        title = ""
    if not title:
        title = doc_id or pdf_path.stem

    date_match = re.search(r'(\d{4}-\d{2}-\d{2})', cover_text)
    issue_date = date_match.group(1) if date_match else ""

    return {"doc_id": doc_id, "version": version, "title": title, "issue_date": issue_date}
