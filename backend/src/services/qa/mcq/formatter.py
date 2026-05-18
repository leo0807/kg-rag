from __future__ import annotations

from typing import Any


_TYPE_LABELS = {
    "T3_order": "步骤顺序题",
    "T1_definition": "概念/目的题",
    "T4_numeric": "数值/规格题",
    "T6_condition": "条件/判据题",
    "T0_general": "客观题",
}

_PRIORITY_LABELS = {
    "P1": "规范明文依据",
    "P2": "工艺逻辑推断",
}


def format_mcq_answer_md(meta: dict[str, Any], options: dict[str, str]) -> str:
    lines: list[str] = []
    type_label = _TYPE_LABELS.get(str(meta.get("mcq_type") or ""), "客观题")
    lines.append(f"**题目类型**：{type_label}")

    if priority := str(meta.get("priority_used") or "").strip():
        lines.append(f"**判定依据**：{_PRIORITY_LABELS.get(priority, priority)}")

    if evidence := str(meta.get("evidence_quote") or "").strip():
        lines.append(f"\n**规范依据**：\n> {evidence}")

    step_analysis = meta.get("step_analysis")
    if isinstance(step_analysis, dict) and step_analysis:
        lines.append("\n**步骤分析**：")
        for key in sorted(step_analysis.keys()):
            value = step_analysis.get(key)
            if value:
                lines.append(f"- {value}")

    category_analysis = meta.get("category_analysis")
    if isinstance(category_analysis, dict) and category_analysis:
        lines.append("\n**范畴分析**：")
        for letter in options:
            items = category_analysis.get(letter) or []
            if not isinstance(items, list) or not items:
                continue
            parts = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                word = str(item.get("word") or "").strip()
                category = str(item.get("category") or "").strip()
                if word and category:
                    parts.append(f"{word}（{category}）")
            if parts:
                lines.append(f"- {letter}：{'，'.join(parts)}")

    lines.append("\n**选项分析**：")
    per_option = meta.get("per_option") or meta.get("parsed", {}).get("per_option", {}) or {}
    for letter in options:
        info = per_option.get(letter, {}) if isinstance(per_option, dict) else {}
        decision = str(info.get("decision") or "?").strip()
        reason = str(info.get("reason") or "").strip()
        mark = "✅" if decision == "保留" else "❌" if decision == "排除" else "⚪"
        lines.append(f"- {mark} **{letter}**（{decision}）：{reason}")

    final_answer = (
        str(meta.get("predicted") or meta.get("final_answer") or meta.get("parsed", {}).get("final_answer") or "?")
        .strip()
        .upper()
    )
    lines.append(f"\n**最终答案：{final_answer}**")

    if final_reason := str(meta.get("final_reason") or meta.get("parsed", {}).get("final_reason") or "").strip():
        lines.append(f"\n{final_reason}")

    return "\n".join(lines).strip()
