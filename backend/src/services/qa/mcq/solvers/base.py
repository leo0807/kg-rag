from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator

from src.services.retrieval.reranker import rerank
from src.services.ai.errors import LLMError

from ..parser import MCQParseError, format_mcq_result, parse_mcq_response, validate_mcq_output
from ..types import MCQType, MCQ_TYPE_META

logger = logging.getLogger(__name__)


class BaseMCQSolver(ABC):
    mcq_type: MCQType = MCQType.GENERAL
    require_per_option: bool = False
    template_id: str = "mcq_general"

    def __init__(self, driver, llm, reranker=None):
        self.driver = driver
        self.llm = llm
        self.reranker = reranker

    async def search(self, mcq, doc_id: str = "", top_k: int = 10) -> list[dict[str, Any]]:
        query = mcq.stem.replace("___", "").replace("______", "")
        from src.routers.query.core import do_retrieval
        sections, _, _ = await asyncio.to_thread(
            do_retrieval,
            self.driver,
            query,
            "parallel",
            top_k,
            False,
            0.5,
            doc_id,
            False,
        )
        return sections

    async def rerank(self, sources: list[dict[str, Any]], mcq, top_k: int = 10) -> list[dict[str, Any]]:
        if not sources:
            return []
        try:
            return await asyncio.to_thread(rerank, mcq.stem, sources, top_k)
        except Exception as exc:
            logger.debug("MCQ rerank 失败（跳过）: %s", exc)
            return sources[:top_k]

    @abstractmethod
    async def build_prompt(self, mcq, sources: list[dict[str, Any]]) -> dict[str, Any]:
        raise NotImplementedError

    def parse_output(self, raw_text: str, mcq) -> dict[str, Any]:
        parsed = parse_mcq_response(raw_text)
        validate_mcq_output(parsed, mcq.options, require_per_option=self.require_per_option)
        parsed.setdefault("mcq_type", self.mcq_type.value)
        return parsed

    def format_result(self, parsed: dict[str, Any]) -> str:
        return format_mcq_result(parsed)

    async def solve_streaming(
        self,
        mcq,
        doc_id: str = "",
        top_k: int = 10,
    ) -> AsyncGenerator[dict[str, Any], None]:
        meta = MCQ_TYPE_META[self.mcq_type]
        yield {"type": "stage", "content": {"name": "classify", "label": f"识别为{meta.name}", "progress": 5}}
        yield {"type": "stage", "content": {"name": "retrieve", "label": "检索规范", "progress": 25}}
        sources = await self.search(mcq, doc_id=doc_id, top_k=top_k)
        yield {"type": "sources", "items": [self._src_to_dict(s) for s in sources]}
        yield {"type": "stage", "content": {"name": "rerank", "label": "精排证据", "progress": 45}}
        sources = await self.rerank(sources, mcq, top_k=top_k)
        yield {"type": "stage", "content": {"name": "reason", "label": meta.label, "progress": 65}}

        prompt = await self.build_prompt(mcq, sources)
        messages = prompt.get("messages") or [{"role": "user", "content": prompt.get("user") or ""}]
        raw_chunks: list[str] = []
        try:
            async for delta in self.llm.stream_chat(
                messages,
                max_tokens=prompt.get("max_tokens", 800),
                temperature=prompt.get("temperature", 0.1),
            ):
                if delta:
                    raw_chunks.append(delta)
        except LLMError as exc:
            logger.warning(
                "[%s] LLMError during stream: code=%s msg=%s",
                self.__class__.__name__,
                getattr(exc, "code", None),
                exc,
            )
            yield {
                "type": "error",
                "code": getattr(exc, "code", "llm_error"),
                "status_code": getattr(exc, "status_code", 500),
                "message": str(exc),
            }
            yield {"type": "done", "graceful": False}
            return
        except Exception as exc:
            logger.exception("[%s] unexpected error during stream", self.__class__.__name__)
            yield {
                "type": "error",
                "code": "internal_error",
                "status_code": 500,
                "message": "服务异常，请稍后重试",
            }
            yield {"type": "done", "graceful": False}
            return

        yield {"type": "stage", "content": {"name": "validate", "label": "校验答案", "progress": 95}}
        raw_text = "".join(raw_chunks)
        try:
            parsed = self.parse_output(raw_text, mcq)
            parsed.setdefault("options", mcq.options)
            formatted = self.format_result(parsed)
            yield {
                "type": "answer_meta",
                "mcq_type": self.mcq_type.value,
                "predicted": parsed.get("final_answer") or parsed.get("answer") or "",
                "parsed": parsed,
                "formatted_answer": formatted,
                "formatted_markdown": formatted,
            }
            for line in formatted.splitlines(keepends=True):
                if line:
                    yield {"type": "delta", "content": line}
        except MCQParseError as exc:
            logger.warning("MCQ 解析失败: %s", exc)
            yield {
                "type": "parse_failed",
                "reason": str(exc),
                "raw_text": exc.raw_text[:500],
            }
        yield {"type": "done", "progress": 100}

    async def solve(self, mcq, doc_id: str = "", top_k: int = 10) -> dict[str, Any]:
        sources: list[dict[str, Any]] = []
        answer_meta: dict[str, Any] = {}
        raw_chunks: list[str] = []
        async for event in self.solve_streaming(mcq, doc_id=doc_id, top_k=top_k):
            if event.get("type") == "sources":
                sources = event.get("items") or sources
            elif event.get("type") == "delta":
                raw_chunks.append(str(event.get("content") or ""))
            elif event.get("type") == "answer_meta":
                answer_meta = event
            elif event.get("type") == "parse_failed":
                answer_meta = event
            elif event.get("type") == "error":
                answer_meta = event
        if answer_meta.get("type") == "parse_failed":
            answer = "⚠️ 无法可靠回答这道客观题。\n\n" + str(answer_meta.get('reason', ''))
        elif answer_meta.get("type") == "error":
            answer = "⚠️ 无法可靠回答这道客观题。\n\n" + str(answer_meta.get("message", ""))
        else:
            answer = answer_meta.get("formatted_answer") or answer_meta.get("reason") or ""
        if not answer and raw_chunks:
            answer = "".join(raw_chunks)
        return {
            "answer": answer,
            "predicted": answer_meta.get("predicted") or "",
            "sources": sources,
            "raw_response": "".join(raw_chunks),
            "strategy_used": self.mcq_type.value,
            "mcq_type": self.mcq_type.value,
            "answer_meta": answer_meta,
        }

    @staticmethod
    def _src_to_dict(s: dict[str, Any]) -> dict[str, Any]:
        return {
            "chunk_id": s.get("chunk_id", ""),
            "doc_id": s.get("doc_id", ""),
            "number": s.get("number", ""),
            "title": s.get("title", ""),
            "content": s.get("content", ""),
            "score": float(s.get("score", 0) or 0),
            "page_idx": s.get("page_idx"),
            "bbox": s.get("bbox"),
            "source_type": s.get("source_type", []),
            "retrieval_trace": s.get("retrieval_trace", []),
            "is_graph_expanded": bool(s.get("is_graph_expanded")),
            "is_vector_hit": bool(s.get("is_vector_hit")),
            "is_fulltext_hit": bool(s.get("is_fulltext_hit")),
            "is_gnn_hit": bool(s.get("is_gnn_hit")),
        }
