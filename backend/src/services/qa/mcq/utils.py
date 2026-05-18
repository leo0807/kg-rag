from __future__ import annotations

import re

OPTION_LINE = re.compile(r'^\s*([A-H])[\.、\s]+(.+?)\s*$')


def split_stem_and_options(full_text: str) -> tuple[str, dict[str, str]]:
    stem_lines: list[str] = []
    options: dict[str, str] = {}
    in_options = False
    for line in (full_text or '').splitlines():
        match = OPTION_LINE.match(line)
        if match:
            in_options = True
            options[match.group(1)] = match.group(2).strip()
            continue
        if in_options:
            continue
        stem_lines.append(line)
    return '\n'.join(stem_lines).strip(), options
