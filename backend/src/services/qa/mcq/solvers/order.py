from __future__ import annotations

import re
from typing import Any

from src.prompts import registry

from ..types import MCQType
from ..utils import split_stem_and_options
from .base import BaseMCQSolver


_STEP_RE = re.compile(r"([①②③④⑤⑥⑦⑧⑨])\s*([^①②③④⑤⑥⑦⑧⑨]+?)(?=[①②③④⑤⑥⑦⑧⑨]|$)")


class OrderMCQSolver(BaseMCQSolver):
    mcq_type = MCQType.ORDER
    require_per_option = True
    template_id = 'mcq_order'

    def extract_steps(self, mcq) -> list[str]:
        stem_only, _ = split_stem_and_options(mcq.stem)
        steps = [text.strip().rstrip('。') for _, text in _STEP_RE.findall(stem_only or '')]
        return [step for step in steps if len(step) >= 4]

    async def search(self, mcq, doc_id: str = '', top_k: int = 10) -> list[dict[str, Any]]:
        stem_only, _ = split_stem_and_options(mcq.stem)
        steps = self.extract_steps(mcq)
        query_base = re.sub(r"[①②③④⑤⑥⑦⑧⑨].*", '', stem_only).strip() or stem_only.strip()
        seen: set[str] = set()
        collected: list[dict[str, Any]] = []

        async def _append_from_query(query: str, limit: int) -> None:
            probe = mcq.__class__(stem=query, options=mcq.options)
            sections = await super(OrderMCQSolver, self).search(probe, doc_id=doc_id, top_k=limit)
            for sec in sections:
                cid = str(sec.get('chunk_id') or '')
                if cid and cid in seen:
                    continue
                if cid:
                    seen.add(cid)
                collected.append(sec)

        await _append_from_query(f'{query_base} 推荐 顺序', 5)
        for step in steps:
            await _append_from_query(step, 3)
        return collected[:12]

    async def build_prompt(self, mcq, sources: list[dict[str, Any]]) -> dict[str, Any]:
        stem_only, _ = split_stem_and_options(mcq.stem)
        steps = self.extract_steps(mcq)
        markers = '①②③④⑤⑥⑦'
        steps_text = '\n'.join(
            f'  {markers[idx]} {step}'
            for idx, step in enumerate(steps)
            if idx < len(markers)
        ) or stem_only
        return registry.render(
            self.template_id,
            evidence=self._format_evidence(sources),
            stem=stem_only,
            steps=steps_text,
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
