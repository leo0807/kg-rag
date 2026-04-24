from __future__ import annotations

import json
from typing import Any


def normalize_image_text_values(values: Any) -> list[str]:
    """将图片元数据清洗为可安全拼接的字符串列表。"""
    if values is None:
        return []

    if isinstance(values, str):
        stripped = values.strip()
        if stripped.startswith(("[", "{")):
            try:
                decoded = json.loads(stripped)
            except Exception:
                decoded = values
            values = decoded

    if not isinstance(values, list):
        values = [values]

    result: list[str] = []
    for value in values:
        if value is None:
            continue
        if isinstance(value, str):
            text = value.strip()
        elif isinstance(value, (int, float, bool)):
            text = str(value)
        else:
            text = json.dumps(value, ensure_ascii=False, sort_keys=True)
        if text:
            result.append(text)
    return result


def build_image_milvus_text(
    summary: str,
    part_numbers: Any = None,
    assembly_relations: Any = None,
) -> str:
    """构造图片向量化文本，兼容脏数据类型。"""
    sections: list[str] = []
    base = (summary or "").strip()
    if base:
        sections.append(base)

    normalized_part_numbers = normalize_image_text_values(part_numbers)
    if normalized_part_numbers:
        sections.append("件号: " + ", ".join(normalized_part_numbers))

    normalized_relations = normalize_image_text_values(assembly_relations)
    if normalized_relations:
        sections.append("装配关系: " + "; ".join(normalized_relations))

    return "\n".join(sections)
