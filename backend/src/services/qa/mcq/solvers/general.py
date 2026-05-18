from __future__ import annotations

from typing import Any

from src.prompts import registry

from ..types import MCQType
from .base import BaseMCQSolver


class GeneralMCQSolver(BaseMCQSolver):
    mcq_type = MCQType.GENERAL
    template_id = 'mcq_general'

    async def build_prompt(self, mcq, sources: list[dict[str, Any]]) -> dict[str, Any]:
        return registry.render(
            self.template_id,
            evidence=self._format_evidence(sources),
            stem=mcq.stem,
            options='\n'.join(f'{k}. {v}' for k, v in mcq.options.items()),
        )

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
