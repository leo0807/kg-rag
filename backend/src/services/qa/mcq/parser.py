from __future__ import annotations

import json
import re
from typing import Any

from .formatter import format_mcq_answer_md

BANNED_PHRASES = [
    '语义类型不一致',
    '与题意不符',
    '与题目要求的语义类型不一致',
    '已检索相关规范章节',
]


class MCQParseError(Exception):
    def __init__(self, raw_text: str, reason: str = ''):
        self.raw_text = raw_text or ''
        self.reason = reason
        super().__init__(f'MCQ 解析失败: {reason}; 原始输出前200字={self.raw_text[:200]!r}')


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r'^```json\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^```\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    return text.strip()


def _normalize_answer(answer: Any) -> str:
    if not isinstance(answer, str):
        return ''
    return answer.strip().upper().translate(str.maketrans('ＡＢＣＤＥＦＧＨ', 'ABCDEFGH'))


def parse_mcq_response(raw_text: str) -> dict[str, Any]:
    text = _strip_code_fences(raw_text)
    if not text:
        raise MCQParseError(raw_text, 'empty response')

    blob = text
    if not blob.startswith('{'):
        match = re.search(r'\{[\s\S]*\}', text)
        if not match:
            raise MCQParseError(raw_text, 'no json object found')
        blob = match.group(0)

    try:
        parsed = json.loads(blob)
    except json.JSONDecodeError as exc:
        raise MCQParseError(raw_text, f'JSON 解析失败: {exc}') from exc

    if not isinstance(parsed, dict):
        raise MCQParseError(raw_text, 'JSON 顶层不是对象')

    answer = _normalize_answer(parsed.get('final_answer') or parsed.get('answer') or '')
    if answer:
        parsed['final_answer'] = answer
    return parsed


def validate_mcq_output(parsed: dict[str, Any], options: dict[str, str], require_per_option: bool = False) -> None:
    answer = _normalize_answer(parsed.get('final_answer') or parsed.get('answer') or '')
    if not answer:
        raise MCQParseError(json.dumps(parsed, ensure_ascii=False), '缺少 final_answer/answer')
    if answer not in options:
        raise MCQParseError(json.dumps(parsed, ensure_ascii=False), f'final_answer={answer!r} 不在选项中')

    per_option = parsed.get('per_option')
    if per_option is None:
        if require_per_option:
            raise MCQParseError(json.dumps(parsed, ensure_ascii=False), '缺少 per_option')
        reason = str(parsed.get('reason') or parsed.get('final_reason') or '').strip()
        if not reason:
            raise MCQParseError(json.dumps(parsed, ensure_ascii=False), '缺少 reason')
        if any(b in reason for b in BANNED_PHRASES):
            raise MCQParseError(json.dumps(parsed, ensure_ascii=False), 'reason 包含禁用短语')
        return

    if not isinstance(per_option, dict):
        raise MCQParseError(json.dumps(parsed, ensure_ascii=False), 'per_option 不是对象')
    if set(per_option.keys()) != set(options.keys()):
        raise MCQParseError(json.dumps(parsed, ensure_ascii=False), f'per_option 键 {sorted(per_option.keys())} 与选项 {sorted(options.keys())} 不匹配')

    reasons: list[str] = []
    for letter in sorted(options.keys()):
        item = per_option.get(letter) or {}
        if not isinstance(item, dict):
            raise MCQParseError(json.dumps(parsed, ensure_ascii=False), f'{letter} 不是对象')
        reason = str(item.get('reason') or '').strip()
        if not reason:
            raise MCQParseError(json.dumps(parsed, ensure_ascii=False), f'{letter} 缺少 reason')
        if len(reason) < 15:
            raise MCQParseError(json.dumps(parsed, ensure_ascii=False), f'{letter} reason 过短')
        if any(b in reason for b in BANNED_PHRASES):
            raise MCQParseError(json.dumps(parsed, ensure_ascii=False), f'{letter} reason 包含禁用短语')
        reasons.append(reason)

    if len(set(reasons)) < len(reasons):
        raise MCQParseError(json.dumps(parsed, ensure_ascii=False), 'per_option 有重复 reason')

    keep_reasons = [str(v.get('reason') or '') for v in per_option.values() if str(v.get('decision') or '').strip() == '保留']
    drop_reasons = [str(v.get('reason') or '') for v in per_option.values() if str(v.get('decision') or '').strip() == '排除']
    if any(reason in drop_reasons for reason in keep_reasons):
        raise MCQParseError(json.dumps(parsed, ensure_ascii=False), '保留与排除 reason 不能相同')


def format_mcq_result(parsed: dict[str, Any]) -> str:
    return format_mcq_answer_md(parsed, parsed.get('options', {}) if isinstance(parsed.get('options'), dict) else {})
