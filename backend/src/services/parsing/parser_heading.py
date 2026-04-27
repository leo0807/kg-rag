from __future__ import annotations

import re

from .parser_patterns import (
    SECTION_PATTERNS,
    _TOC_HINT_RE, _TOC_TRAIL_RE, _PAGE_TRAIL_RE,
    _BODY_ITEM_RE, _UNIT_ONLY_RE, _CATALOG_HINT_RE,
    _MODEL_CODE_TOKEN_RE, _TITLE_CONTINUATION_RE,
    _TRAILING_CONNECTOR_RE, _REFERENCE_TITLE_RE,
)


def fix_token_spacing(text: str) -> str:
    text = re.sub(r'([0-9A-Za-z\.])([\u4e00-\u9fff\u3400-\u4dbf])', r'\1 \2', text)
    text = re.sub(r'([\u4e00-\u9fff\u3400-\u4dbf])([0-9A-Za-z])', r'\1 \2', text)
    return text


def _looks_like_toc(title: str) -> bool:
    t = re.sub(r'\s+', ' ', title).strip()
    if not t:
        return False
    if _TOC_HINT_RE.search(t):
        return True
    if _TOC_TRAIL_RE.search(t):
        return True
    if _PAGE_TRAIL_RE.search(t) and len(t) <= 48:
        return True
    return False


def _is_likely_toc_page(lines: list[str]) -> bool:
    normalized = [re.sub(r'\s+', ' ', line).strip() for line in lines if line.strip()]
    if not normalized:
        return False
    if any(_TOC_HINT_RE.search(line) for line in normalized):
        return True
    toc_like_lines = sum(1 for line in normalized if _looks_like_toc(line))
    heading_with_page_trail = sum(
        1 for line in normalized
        if _match_section_heading(line) and _PAGE_TRAIL_RE.search(line)
    )
    return toc_like_lines >= 4 or heading_with_page_trail >= 3


def _table_bbox_list(page) -> list[list[float]]:
    try:
        tables = page.find_tables() or []
    except Exception:
        return []
    out: list[list[float]] = []
    for table in tables:
        bbox = getattr(table, "bbox", None)
        if not bbox or len(bbox) != 4:
            continue
        out.append([float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])])
    return out


def _bbox_overlap_ratio(a: list[float], b: list[float]) -> float:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    ix0 = max(ax0, bx0); iy0 = max(ay0, by0)
    ix1 = min(ax1, bx1); iy1 = min(ay1, by1)
    if ix1 <= ix0 or iy1 <= iy0:
        return 0.0
    area = max((ax1 - ax0) * (ay1 - ay0), 1.0)
    return ((ix1 - ix0) * (iy1 - iy0)) / area


def _line_overlaps_table(line_bbox: list[float], table_bboxes: list[list[float]]) -> bool:
    for table_bbox in table_bboxes:
        if _bbox_overlap_ratio(line_bbox, table_bbox) >= 0.45:
            return True
    return False


def _extract_page_tables(page) -> list[dict]:
    tables: list[dict] = []
    try:
        for table in page.find_tables() or []:
            rows = table.extract() or []
            tables.append({"rows": rows, "bbox": list(table.bbox) if getattr(table, "bbox", None) else None})
    except Exception:
        tables = []
    if tables:
        return tables
    try:
        raw_tables = page.extract_tables() or []
    except Exception:
        raw_tables = []
    return [{"rows": rows, "bbox": None} for rows in raw_tables]


def _match_section_heading(text: str) -> tuple[str, str] | None:
    candidate = (text or "").strip()
    if not candidate:
        return None
    for pat in SECTION_PATTERNS:
        match = pat.match(candidate)
        if match:
            return match.group(1), match.group(2).strip()
    text_fixed = re.sub(r'(\d)\s*\.\s*(\d)', r'\1.\2', candidate)
    if text_fixed != candidate:
        for pat in SECTION_PATTERNS:
            match = pat.match(text_fixed)
            if match:
                return match.group(1), match.group(2).strip()
    return None


def is_likely_section_title(number: str, title: str) -> bool:
    title = title.strip()
    normalized_title = re.sub(r'\s+', ' ', title)
    if _looks_like_toc(title):
        return False
    if _UNIT_ONLY_RE.fullmatch(normalized_title):
        return False
    if re.search(r'\.{3,}', title):
        return False
    if _BODY_ITEM_RE.search(title):
        return False
    if len(title) > 70 and not re.match(r'^[\u4e00-\u9fff\w─—]{2,20}[（(：: ─—]', title):
        return False
    parts = number.split(".")
    if len(parts) == 2 and len(parts[1]) >= 3 and parts[1].isdigit():
        return False
    if number == "0" or number.startswith("0."):
        return False
    if re.match(r'^0\d$', number):
        return False
    if re.search(
        r'\d+\s*[（(]?\s*\d*\.?\d*\s*(lbf|N·m|N\.m|nm|kg|mm|cm|MPa|kPa|°C|℃|psi|rpm|Hz|in\b)',
        title, re.IGNORECASE,
    ):
        return False
    if re.search(r'如图\s*[\d\w]+[-–]\d+[^。]*所示\s*[；;，,。]?\s*$', title):
        return False
    if re.search(r'[周米克吨磅英寸毫米厘米秒分钟小时]\s*[，,；;。]?\s*$', title):
        return False
    stripped = re.sub(r'[；;，,。.!！?？\s]', '', title)
    if len(stripped) < 4 and not re.fullmatch(r'[\u4e00-\u9fff]{2,3}', stripped):
        return False
    if re.match(r'^[\d\s/\-–—.]+$', title):
        return False
    visible = re.sub(r'\s+', '', normalized_title)
    natural_chars = len(re.findall(r'[\u4e00-\u9fffA-Za-z]', normalized_title))
    code_tokens = _MODEL_CODE_TOKEN_RE.findall(normalized_title)
    digit_groups = re.findall(r'\d+(?:\.\d+)?', normalized_title)
    if (
        _CATALOG_HINT_RE.search(normalized_title)
        or (code_tokens and natural_chars < max(6, int(len(visible) * 0.45))
            and re.search(r'[\d#/\-–—]', normalized_title))
    ):
        return False
    if (
        re.search(r'\bN/?A\b', normalized_title, re.IGNORECASE)
        or normalized_title.startswith(("(", "（"))
        or (natural_chars <= 3 and len(digit_groups) >= 2 and re.search(r'[()/#\-–—]', normalized_title))
        or (natural_chars <= 4 and len(digit_groups) >= 1 and re.search(r'[()（）]', normalized_title))
    ):
        return False
    if normalized_title.endswith(("-", "–", "—")):
        return False
    if re.fullmatch(r'[a-z][a-z\-]{1,20}', normalized_title):
        return False
    alpha_tokens = re.findall(r'[A-Za-z]+', normalized_title)
    digit_tokens = re.findall(r'\d+', normalized_title)
    if (
        not re.search(r'[\u4e00-\u9fff]', normalized_title)
        and len(alpha_tokens) >= 2
        and all(len(token) == 1 for token in alpha_tokens)
        and (digit_tokens or re.search(r'[#/\\\-–—]', normalized_title))
    ):
        return False
    if re.search(r'[\\|]{2,}', title):
        return False
    if len(re.findall(r'[\u4e00-\u9fffA-Za-z]', title)) < 2:
        return False
    if re.match(r'^(图|表)\s*\d+', title):
        return False
    return True


def _normalize_anchor_number(number: str) -> str:
    normalized = (number or "").strip()
    normalized = normalized.rstrip("、.．)）")
    return normalized


def _section_number_key(number: str) -> tuple[int, ...]:
    normalized = _normalize_anchor_number(number)
    if not normalized:
        return tuple()
    try:
        return tuple(int(part) for part in normalized.split("."))
    except ValueError:
        return tuple()


def _normalize_heading_candidate(text: str, on_toc_page: bool) -> str:
    candidate = (text or "").strip()
    if not candidate or on_toc_page:
        return candidate
    match = _match_section_heading(candidate)
    if not match:
        return candidate
    number, title = match
    trimmed_title = _PAGE_TRAIL_RE.sub("", title).strip()
    if not trimmed_title or trimmed_title == title:
        return candidate
    if not is_likely_section_title(number, trimmed_title):
        return candidate
    return f"{number} {trimmed_title}"


def _should_extend_heading_title(title: str) -> bool:
    normalized = re.sub(r'\s+', ' ', (title or "")).strip()
    if not normalized:
        return False
    if normalized.count("(") > normalized.count(")"):
        return True
    if normalized.count("（") > normalized.count("）"):
        return True
    if _TITLE_CONTINUATION_RE.search(normalized):
        return True
    if _TRAILING_CONNECTOR_RE.search(normalized):
        return True
    return False


def _merge_wrapped_heading(current_text: str, next_text: str) -> tuple[str, str] | None:
    current_match = _match_section_heading(current_text)
    if not current_match:
        return None
    number, title = current_match
    if not _should_extend_heading_title(title):
        return None
    next_normalized = re.sub(r'\s+', ' ', (next_text or "")).strip()
    if not next_normalized:
        return None
    if _match_section_heading(next_normalized):
        return None
    merged_match = _match_section_heading(f"{current_text} {next_normalized}")
    if not merged_match:
        return None
    return merged_match
