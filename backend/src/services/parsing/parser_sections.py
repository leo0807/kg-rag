from __future__ import annotations

import logging
import pdfplumber
from pathlib import Path

from .parser_heading import (
    fix_token_spacing,
    _table_bbox_list,
    _line_overlaps_table,
    _match_section_heading,
    _normalize_heading_candidate,
    _merge_wrapped_heading,
    _is_likely_toc_page,
    is_likely_section_title,
)
from .parser_toc import (
    _collect_toc_numbers_from_all_lines,
    _postprocess_headings,
    _trim_front_matter_sections,
)
from .parser_meta import clean_content, clean_ocr_artifacts
from .parser_patterns import SECTION_PATTERNS

logger = logging.getLogger(__name__)


def extract_sections(pdf_path: Path, doc_id: str) -> list[dict]:
    sections = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            all_lines = []
            for page_idx, page in enumerate(pdf.pages):
                words = page.extract_words()
                table_bboxes = _table_bbox_list(page)
                if not words:
                    continue

                words.sort(key=lambda w: (w["top"], w["x0"]))
                curr_line = [words[0]]
                lines_in_page = []
                for w in words[1:]:
                    if abs(w["top"] - curr_line[-1]["top"]) < 3:
                        curr_line.append(w)
                    else:
                        lines_in_page.append(curr_line)
                        curr_line = [w]
                lines_in_page.append(curr_line)

                def _line_to_text(words_in_line: list[dict]) -> str:
                    ordered_words = sorted(words_in_line, key=lambda w: w["x0"])
                    raw_text = " ".join(w["text"] for w in ordered_words).strip()
                    return fix_token_spacing(raw_text)

                page_line_texts = [_line_to_text(line) for line in lines_in_page]
                page_is_toc = _is_likely_toc_page(page_line_texts)

                line_idx = 0
                while line_idx < len(lines_in_page):
                    line_words = lines_in_page[line_idx]
                    text = _normalize_heading_candidate(page_line_texts[line_idx], page_is_toc)
                    heading = _match_section_heading(text)
                    consumed_lines = 1
                    bbox_words = line_words

                    if heading and line_idx + 1 < len(lines_in_page):
                        next_words = lines_in_page[line_idx + 1]
                        next_text = _normalize_heading_candidate(
                            page_line_texts[line_idx + 1], page_is_toc
                        )
                        merged_heading = _merge_wrapped_heading(text, next_text)
                        if merged_heading:
                            heading = merged_heading
                            consumed_lines = 2
                            bbox_words = sorted(line_words + next_words, key=lambda w: (w["top"], w["x0"]))

                    bbox = [
                        min(w["x0"] for w in bbox_words),
                        min(w["top"] for w in bbox_words),
                        max(w["x1"] for w in bbox_words),
                        max(w["bottom"] for w in bbox_words),
                    ]
                    is_in_table = _line_overlaps_table(bbox, table_bboxes)

                    if heading and not is_in_table and is_likely_section_title(heading[0], heading[1]):
                        all_lines.append({
                            "type": "heading", "number": heading[0], "title": heading[1],
                            "page_idx": page_idx, "bbox": bbox, "global_pos": len(all_lines),
                        })
                    elif heading and page_is_toc and not is_in_table:
                        all_lines.append({
                            "type": "toc_heading", "number": heading[0], "title": heading[1],
                            "page_idx": page_idx,
                        })
                        all_lines.append({"type": "text", "content": text, "page_idx": page_idx})
                    else:
                        all_lines.append({"type": "text", "content": text, "page_idx": page_idx})
                    line_idx += consumed_lines

            headings = [line for line in all_lines if line["type"] == "heading"]
            headings = [
                h for h in headings
                if len(h["title"].strip()) >= 2
                and h["title"].strip() != '_'
                and not h["title"].strip().replace('.', '').replace(' ', '').isdigit()
            ]
            _seen_nums: set[str] = set()
            _deduped_rev: list[dict] = []
            for h in reversed(headings):
                if h["number"] not in _seen_nums:
                    _seen_nums.add(h["number"])
                    _deduped_rev.append(h)
            headings = list(reversed(_deduped_rev))
            toc_numbers = _collect_toc_numbers_from_all_lines(all_lines)
            headings = _postprocess_headings(headings, toc_numbers)

            for i, h in enumerate(headings):
                start_idx = h["global_pos"]
                end_idx = headings[i + 1]["global_pos"] if i + 1 < len(headings) else len(all_lines)
                content_parts = []
                for j in range(start_idx, end_idx):
                    line = all_lines[j]
                    if line["type"] == "text":
                        content_parts.append(line["content"])
                    elif line["type"] == "heading" and j == start_idx:
                        content_parts.append(f"{line['number']} {line['title']}")
                raw_content = "\n".join(content_parts)
                safe_num = h["number"].replace(".", "_")
                sections.append({
                    "chunk_id": f"{doc_id}_{safe_num}",
                    "number":   h["number"],
                    "title":    clean_ocr_artifacts(h["title"]),
                    "content":  clean_content(raw_content),
                    "level":    len(h["number"].split(".")),
                    "seq_index": i,
                    "page_idx": h["page_idx"],
                    "bbox":     h["bbox"],
                })

    except Exception as e:
        logger.error("提取章节坐标失败: %s", e)
        return _extract_sections_legacy(pdf_path, doc_id)

    if not sections:
        return _extract_sections_legacy(pdf_path, doc_id)
    return _trim_front_matter_sections(sections)


def _extract_sections_legacy(pdf_path: Path, doc_id: str) -> list[dict]:
    with pdfplumber.open(pdf_path) as pdf:
        full_text = ""
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            page_lines = [
                fix_token_spacing(line.strip())
                for line in page_text.split('\n')
                if line.strip()
            ]
            page_is_toc = _is_likely_toc_page(page_lines)
            normalized_lines = [
                _normalize_heading_candidate(line, page_is_toc)
                for line in page_lines
            ]
            full_text += "\n".join(normalized_lines) + "\n"

    all_matches: list[tuple[int, object]] = []
    seen_starts: set[int] = set()
    toc_numbers: set[str] = set()
    for pat in SECTION_PATTERNS:
        for m in pat.finditer(full_text):
            if m.start() not in seen_starts:
                seen_starts.add(m.start())
                all_matches.append((m.start(), m))
    all_matches.sort(key=lambda x: x[0])

    matches = [
        m for _, m in all_matches
        if len(m.group(2).strip()) >= 2
        and m.group(2).strip() != '_'
        and not m.group(2).strip().replace('.', '').replace(' ', '').isdigit()
        and is_likely_section_title(m.group(1), m.group(2).strip())
    ]

    seen_numbers: set[str] = set()
    deduped_matches = []
    for m in matches:
        n = m.group(1)
        if n not in seen_numbers:
            seen_numbers.add(n)
            deduped_matches.append(m)
    matches = deduped_matches

    match_items = [
        {"number": m.group(1), "title": m.group(2).strip(), "_match": m}
        for m in matches
    ]
    from .parser_toc import _postprocess_headings
    match_items = _postprocess_headings(match_items, toc_numbers)
    matches = [item["_match"] for item in match_items]

    sections = []
    for i, match in enumerate(matches):
        number = match.group(1)
        title = match.group(2).strip()
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
        content = clean_content(full_text[start:end])
        safe_num = number.replace(".", "_")
        sections.append({
            "chunk_id": f"{doc_id}_{safe_num}",
            "number":   number,
            "title":    clean_ocr_artifacts(title),
            "content":  content,
            "level":    len(number.split(".")),
            "seq_index": i,
        })
    return _trim_front_matter_sections(sections)
