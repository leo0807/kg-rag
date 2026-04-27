from __future__ import annotations

import re

from .parser_heading import (
    _looks_like_toc,
    _normalize_anchor_number,
    _section_number_key,
    _match_section_heading,
)
from .parser_patterns import _REFERENCE_TITLE_RE


def _collect_toc_numbers_from_all_lines(all_lines: list[dict]) -> set[str]:
    first_scope_page: int | None = None
    for line in all_lines:
        if line.get("type") != "heading":
            continue
        number = _normalize_anchor_number(str(line.get("number", "")))
        title = str(line.get("title", "")).strip()
        if number == "1" and re.search(r"(范围|scope)", title, re.IGNORECASE):
            first_scope_page = int(line.get("page_idx", 0))
            break

    max_toc_page = first_scope_page if first_scope_page is not None else 10
    toc_numbers: set[str] = set()
    for line in all_lines:
        if line.get("type") != "toc_heading":
            continue
        if int(line.get("page_idx", 0)) > max_toc_page:
            continue
        normalized = _normalize_anchor_number(str(line.get("number", "")))
        if normalized:
            toc_numbers.add(normalized)
    return toc_numbers


def _filter_headings_with_toc_anchors(
    headings: list[dict],
    toc_numbers: set[str],
) -> list[dict]:
    if not headings or not toc_numbers:
        return headings
    filtered: list[dict] = []
    toc_top_levels = {number for number in toc_numbers if number.isdigit()}
    for heading in headings:
        number = _normalize_anchor_number(str(heading.get("number", "")))
        title = str(heading.get("title", "")).strip()
        if (
            number.isdigit()
            and len(number) >= 2
            and number not in toc_top_levels
            and not _looks_like_toc(title)
        ):
            continue
        filtered.append(heading)
    return filtered


def _prune_out_of_order_reference_noise(
    headings: list[dict],
    toc_numbers: set[str],
) -> list[dict]:
    if len(headings) < 3:
        return headings
    pruned: list[dict] = []
    for idx, heading in enumerate(headings):
        if idx == 0 or idx == len(headings) - 1:
            pruned.append(heading)
            continue
        number = _normalize_anchor_number(str(heading.get("number", "")))
        title = re.sub(r'\s+', ' ', str(heading.get("title", "")).strip())
        current_key = _section_number_key(number)
        prev_key = _section_number_key(str(headings[idx - 1].get("number", "")))
        next_key = _section_number_key(str(headings[idx + 1].get("number", "")))
        if (
            current_key and prev_key and next_key
            and current_key < prev_key and current_key < next_key
            and number not in toc_numbers
            and (
                _REFERENCE_TITLE_RE.search(title)
                or re.search(r'(?:参见|按.*节|见.*节|refer to|as per section)', title, re.IGNORECASE)
            )
        ):
            continue
        pruned.append(heading)
    return pruned


def _trim_front_matter_headings(headings: list[dict]) -> list[dict]:
    if not headings:
        return headings
    for idx, heading in enumerate(headings):
        number = _normalize_anchor_number(str(heading.get("number", "")))
        title = str(heading.get("title", "")).strip()
        if number == "1" and re.search(r"(范围|scope)", title, re.IGNORECASE):
            return headings[idx:]
    anchor_idx = None
    for idx, heading in enumerate(headings):
        number = _normalize_anchor_number(str(heading.get("number", "")))
        if number == "1":
            anchor_idx = idx
            lookahead = [
                _normalize_anchor_number(str(item.get("number", "")))
                for item in headings[idx + 1: idx + 6]
            ]
            if "2" in lookahead:
                break
    if anchor_idx is None or anchor_idx == 0:
        return headings
    return headings[anchor_idx:]


def _postprocess_headings(headings: list[dict], toc_numbers: set[str]) -> list[dict]:
    headings = _filter_headings_with_toc_anchors(headings, toc_numbers)
    headings = _trim_front_matter_headings(headings)
    headings = _prune_out_of_order_reference_noise(headings, toc_numbers)
    return headings
