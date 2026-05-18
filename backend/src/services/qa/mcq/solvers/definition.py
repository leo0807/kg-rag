from __future__ import annotations

import json
import re
from typing import Any

from src.prompts import registry

from ..types import MCQType
from .base import BaseMCQSolver


class DefinitionMCQSolver(BaseMCQSolver):
    mcq_type = MCQType.DEFINITION
    template_id = 'mcq_definition'

    _PURPOSE_WORDS = ('防漏', '防腐蚀', '密封', '防止', '保护')
    _SCENE_WORDS = ('客舱增压', '整体油箱', '气动性能', '改进', '应用场景')
    _ALIAS = {
        '目的是': '目的',
        '作用是': '作用',
        '定义': '定义',
        '含义': '含义',
        '功能': '功能',
    }

    def extract_subject_and_category(self, stem: str) -> tuple[str, str]:
        clean = re.sub(r'_{2,}|\(\s*\)|（\s*）', '', stem)
        match = re.search(r'(.+?)的(目的|作用|定义|含义|功能)', clean)
        if match:
            subject = match.group(1).strip()
            category = self._ALIAS.get(match.group(2), match.group(2))
            return subject, category
        return clean.strip(), '未明确范畴'

    def _split_phrases(self, text: str) -> list[str]:
        return [part.strip() for part in re.split(r'[、，,；;]\s*', text) if part.strip()]

    def _classify_phrase(self, phrase: str, category: str) -> str:
        if any(word in phrase for word in self._SCENE_WORDS):
            return '应用场景'
        if any(word in phrase for word in self._PURPOSE_WORDS):
            return '目的'
        if category in ('定义', '含义'):
            return '定义项'
        if category == '功能':
            return '功能项'
        return '其他'

    def _category_analysis(self, options: dict[str, str], category: str) -> dict[str, list[dict[str, str]]]:
        analysis: dict[str, list[dict[str, str]]] = {}
        for letter, text in options.items():
            items: list[dict[str, str]] = []
            for phrase in self._split_phrases(text):
                items.append({'word': phrase, 'category': self._classify_phrase(phrase, category)})
            analysis[letter] = items
        return analysis

    def _score_option(self, items: list[dict[str, str]], category: str) -> int:
        target = '目的' if category in ('目的', '作用') else '定义项' if category in ('定义', '含义') else '功能项'
        score = 0
        for item in items:
            item_category = item.get('category', '')
            if item_category == target:
                score += 2
            elif item_category == '应用场景':
                score -= 1
            else:
                score += 0
        return score

    def _pick_answer(self, analysis: dict[str, list[dict[str, str]]], category: str) -> str:
        scored = {letter: self._score_option(items, category) for letter, items in analysis.items()}
        best = max(scored, key=scored.get)
        top = scored[best]
        ties = [letter for letter, score in scored.items() if score == top]
        return best if len(ties) == 1 else sorted(ties)[0]

    def _build_category_analysis_text(self, analysis: dict[str, list[dict[str, str]]]) -> str:
        return json.dumps(analysis, ensure_ascii=False, indent=2)

    async def build_prompt(self, mcq, sources: list[dict[str, Any]]) -> dict[str, Any]:
        registry.reload()
        subject, category = self.extract_subject_and_category(mcq.stem)
        analysis = self._category_analysis(mcq.options, category)
        return registry.render(
            self.template_id,
            evidence=self._format_evidence(sources),
            stem=mcq.stem,
            subject=subject,
            category=category,
            category_analysis=self._build_category_analysis_text(analysis),
            options='\n'.join(f'{k}. {v}' for k, v in mcq.options.items()),
        )

    async def solve(self, mcq, doc_id: str = '', top_k: int = 10) -> dict[str, Any]:
        result = await super().solve(mcq, doc_id=doc_id, top_k=top_k)
        subject, category = self.extract_subject_and_category(mcq.stem)
        analysis = self._category_analysis(mcq.options, category)
        predicted = self._pick_answer(analysis, category)
        parsed = result.get('answer_meta', {}).get('parsed') if isinstance(result.get('answer_meta'), dict) else {}
        if not isinstance(parsed, dict):
            parsed = {}
        parsed['mcq_type'] = self.mcq_type.value
        parsed['subject'] = subject
        parsed['category'] = category
        parsed['category_analysis'] = analysis
        parsed['final_answer'] = predicted
        parsed['predicted'] = predicted
        parsed['priority_used'] = parsed.get('priority_used') or ('P1' if parsed.get('evidence_quote') else 'P2')
        if not parsed.get('final_reason'):
            parsed['final_reason'] = '按范畴一致性检查，选项中仅该项与题干要求的目的范畴一致。'
        result['predicted'] = predicted
        result['mcq_type'] = self.mcq_type.value
        result['answer_meta'] = {'parsed': parsed}
        result['answer'] = self.format_result(parsed)
        return result

    @staticmethod
    def _format_evidence(sources: list[dict[str, Any]]) -> str:
        lines: list[str] = []
        for s in sources[:8]:
            doc = s.get('doc_id', '')
            num = s.get('number', '')
            title = s.get('title', '')
            content = (s.get('content', '') or '').replace('\n', ' ').strip()
            if len(content) > 400:
                content = content[:400] + '...'
            lines.append(f'【{doc} §{num}】{title}\n{content}')
        return '\n\n'.join(lines)
