from __future__ import annotations

import json
import re
from typing import Any

from .mcq_handler import clean_mcq_output, extract_answer_letter

_JSON_BLOCK_RE = re.compile(r"\{[\s\S]*\}", re.DOTALL)


class MCQParseError(Exception):
    """LLM 输出无法解析为合规 MCQ 结果"""

    def __init__(self, raw_text: str, reason: str = ""):
        self.raw_text = raw_text
        self.reason = reason
        super().__init__(
            f"MCQ 解析失败: {reason}; 原始输出前200字={raw_text[:200]!r}"
        )


def parse_mcq_response(llm_text: str, option_labels: list[str]) -> dict[str, Any]:
    text = clean_mcq_output(llm_text or "")
    text = text.strip()
    text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    match = _JSON_BLOCK_RE.search(text)
    payload_text = match.group(0) if match else text
    try:
        data = json.loads(payload_text)
    except Exception:
        try:
            data = json.loads(payload_text.replace('\\"', '"'))
        except Exception as exc:
            raise MCQParseError(text, f"JSON 解析失败: {exc}") from exc

    answer = extract_answer_letter(str(data.get("answer", "")), {label: label for label in option_labels})
    if not answer:
        raise MCQParseError(text, "未能提取合法答案字母")
    return {"answer": answer, "raw_data": data, "raw": text}


def validate_mcq_output(payload: dict[str, Any] | None, option_labels: list[str]) -> bool:
    if not payload or not payload.get("raw_data"):
        return False
    data = payload["raw_data"]
    answer = str(payload.get("answer") or data.get("answer") or "").strip().upper()
    if answer not in {label.upper() for label in option_labels}:
        return False

    analysis = data.get("analysis")
    if not isinstance(analysis, dict):
        return False

    banned_phrases = (
        "语义类型不一致",
        "与题意不符",
        "未找到直接依据",
    )
    raw_text = str(payload.get("raw") or "")
    if any(phrase in raw_text for phrase in banned_phrases):
        return False

    reason_signatures: list[str] = []
    for letter in option_labels:
        info = analysis.get(letter) or {}
        if not isinstance(info, dict):
            return False
        verdict = str(info.get("status") or info.get("verdict") or "").strip()
        reason = str(info.get("reason") or "").strip()
        keywords = str(info.get("keywords") or "").strip()
        evidence = str(info.get("evidence") or "").strip()
        signature = " | ".join([verdict, reason, keywords, evidence]).strip(" |")
        if not signature:
            return False
        reason_signatures.append(signature)
        if any(phrase in signature for phrase in banned_phrases):
            return False

    if len(set(reason_signatures)) < len(reason_signatures):
        return False
    return True


def format_mcq_result(data: dict[str, Any]) -> str:
    lines = ["## 选项分析"]
    verdict_emoji = {"一致": "✅", "矛盾": "❌", "无关": "⚪"}
    for letter, info in (data.get("analysis") or {}).items():
        emoji = verdict_emoji.get(str(info.get("verdict", "")).strip(), "❓")
        lines.append(f"**{letter}. {emoji} {info.get('verdict', '未判定')}**")
        if info.get("keywords"):
            lines.append(f"  - 关键词：{info['keywords']}")
        if info.get("evidence"):
            lines.append(f"  - 规范依据：{info['evidence']}")
        lines.append("")
    lines.append("---")
    lines.append(f"## 最终答案：**{data.get('answer', '未确定')}**")
    confidence_emoji = {"高": "🟢", "中": "🟡", "低": "🔴"}
    conf = str(data.get("confidence", "中"))
    lines.append(f"**置信度**：{confidence_emoji.get(conf, '⚪')} {conf}")
    if data.get("reason"):
        lines.append(f"\n**详细理由**：{data['reason']}")
    return "\n".join(lines).strip()
