from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from typing import Any

from ...prompts import registry
from .mcq_handler import (
    clean_mcq_output,
    identify_answer_options,
    split_question_and_options,
)
from .mcq_response_utils import MCQParseError, format_mcq_result, parse_mcq_response, validate_mcq_output

logger = logging.getLogger(__name__)

_OPTION_SPLIT_RE = re.compile(r"[、，,;；/／\s]+")


@dataclass(frozen=True)
class MCQQuestion:
    stem: str
    options: dict[str, str]


def build_mcq_question(question: str) -> MCQQuestion | None:
    stem, opts = split_question_and_options(question)
    if not opts:
        return None
    return MCQQuestion(stem=stem, options=opts)


def _split_option_parts(text: str) -> list[str]:
    parts = [p.strip(" 、,，;；:/／\t") for p in _OPTION_SPLIT_RE.split(text or "") if p.strip(" 、,，;；:/／\t")]
    return parts or [text.strip()]


def _build_prompt_data(mcq: MCQQuestion, evidence_text: str):
    return registry.render(
        "qa_mcq",
        evidence_text=evidence_text,
        question=mcq.stem,
        options_text=chr(10).join(f"{k}. {v}" for k, v in mcq.options.items()),
        answer_format="选项字母",
    )


def _collect_evidence(sections: list[dict[str, Any]]) -> str:
    evidence_lines: list[str] = []
    for sec in sections[:6]:
        number = sec.get("number") or ""
        title = sec.get("title") or ""
        content = (sec.get("content") or "").replace("\n", " ").strip()
        if len(content) > 120:
            content = content[:120] + "..."
        evidence_lines.append(f"[{sec.get('doc_id', '')} §{number}] {title}\n{content}")
    return "\n\n".join(evidence_lines)


def _serialize_answer_meta(parsed_payload: dict[str, Any], raw_text: str) -> dict[str, Any]:
    return {
        "type": "answer_meta",
        "content": {
            "answer": parsed_payload.get("answer", ""),
            "formatted": format_mcq_result(parsed_payload["raw_data"]),
            "raw_data": parsed_payload.get("raw_data"),
            "raw_text": raw_text,
        },
    }


async def _maybe_rerank_sections(question: str, sections: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
    try:
        from ...services.retrieval.reranker import rerank

        return await asyncio.to_thread(rerank, question, sections, top_k)
    except Exception as exc:
        logger.debug("MCQ rerank 失败（跳过）: %s", exc)
        return sections[:top_k]


def _build_failure_result(
    mcq: MCQQuestion,
    sections: list[dict[str, Any]],
    raw_response: str,
    reason: str = "",
) -> dict[str, Any]:
    message = "⚠️ 无法可靠回答这道客观题。\n\nLLM 输出未能解析为合规格式。请重试或换一种检索策略（如 Agent 模式）。"
    if reason:
        message += f"\n\n调试信息: {reason}"
    return {
        "answer": message,
        "predicted": "",
        "sources": sections,
        "evidence_text": _collect_evidence(sections),
        "raw_response": raw_response,
        "raw_data": None,
        "formatted": message,
        "strategy_used": "mcq_elimination",
        "parse_failed": True,
    }


async def solve_mcq_with_elimination(
    mcq: MCQQuestion,
    retriever,
    llm,
    doc_id: str = "",
    top_k: int = 10,
) -> dict[str, Any]:
    from ...routers.query.core import do_retrieval

    candidate_options = identify_answer_options(mcq.options)
    mcq = MCQQuestion(stem=mcq.stem, options=candidate_options)
    sections, _, _ = await asyncio.to_thread(
        do_retrieval,
        retriever,
        mcq.stem,
        "parallel",
        top_k,
        False,
        0.5,
        doc_id,
        False,
    )
    option_labels = list(candidate_options.keys())
    evidence_text = _collect_evidence(sections)
    prompt_data = _build_prompt_data(mcq, evidence_text)
    last_response = ""
    last_error: MCQParseError | None = None
    for attempt in range(2):
        try:
            raw = await asyncio.to_thread(
                llm.chat,
                prompt_data["messages"],
                timeout=60,
                max_tokens=prompt_data["max_tokens"],
            )
            last_response = clean_mcq_output(raw or "")
            parsed_payload = parse_mcq_response(last_response, option_labels)
            if validate_mcq_output(parsed_payload, option_labels):
                logger.info(
                    "MCQ解析成功: attempt=%s answer=%s options=%s",
                    attempt + 1,
                    parsed_payload.get("answer", ""),
                    list(candidate_options.keys()),
                )
                return {
                    "answer": parsed_payload.get("formatted") or format_mcq_result(parsed_payload["raw_data"]),
                    "predicted": parsed_payload.get("answer", ""),
                    "sources": sections,
                    "evidence_text": evidence_text,
                    "raw_response": last_response,
                    "raw_data": parsed_payload.get("raw_data"),
                    "formatted": parsed_payload.get("formatted") or format_mcq_result(parsed_payload["raw_data"]),
                    "strategy_used": "mcq_elimination",
                }
            logger.debug(
                "MCQ解析未通过校验: attempt=%s answer=%s raw=%s",
                attempt + 1,
                parsed_payload.get("answer", ""),
                last_response[:200],
            )
            last_error = MCQParseError(last_response, "validation failed")
        except Exception as exc:
            if isinstance(exc, MCQParseError):
                last_error = exc
            else:
                last_error = MCQParseError(last_response or "", f"LLM 调用失败: {exc}")
            logger.warning("MCQ 第%s次解析失败: %s", attempt + 1, last_error)
    logger.warning("MCQ 解析失败: options=%s raw=%s", list(candidate_options.keys()), last_response[:200])
    return _build_failure_result(mcq, sections, last_response, reason=last_error.reason if last_error else "unknown")


async def solve_mcq_streaming(
    mcq: MCQQuestion,
    retriever,
    llm,
    doc_id: str = "",
    top_k: int = 10,
):
    from ...routers.query.core import do_retrieval

    yield {"type": "stage", "content": {"name": "classify", "label": "识别题型", "progress": 5}}
    candidate_options = identify_answer_options(mcq.options)
    mcq = MCQQuestion(stem=mcq.stem, options=candidate_options)
    yield {"type": "status", "content": f"✓ 已解析 {len(candidate_options)} 个选项"}
    yield {"type": "stage", "content": {"name": "retrieve", "label": "检索规范", "progress": 25}}
    sections, _, _ = await asyncio.to_thread(
        do_retrieval,
        retriever,
        mcq.stem,
        "parallel",
        top_k,
        False,
        0.5,
        doc_id,
        False,
    )
    yield {"type": "sources", "content": sections}
    yield {"type": "status", "content": f"✓ 已找到 {len(sections)} 个相关章节"}
    yield {"type": "stage", "content": {"name": "rerank", "label": "精排证据", "progress": 45}}
    sections = await _maybe_rerank_sections(mcq.stem, sections, top_k)
    evidence_text = _collect_evidence(sections)
    prompt_data = _build_prompt_data(mcq, evidence_text)
    option_labels = list(candidate_options.keys())
    last_response = ""
    last_error: MCQParseError | None = None
    for attempt in range(2):
        yield {"type": "stage", "content": {"name": "reason", "label": "推理选项", "progress": 65}}
        buffer_parts: list[str] = []
        try:
            async for chunk in llm.stream_chat(
                prompt_data["messages"],
                timeout=60,
                max_tokens=prompt_data["max_tokens"],
            ):
                if not chunk:
                    continue
                buffer_parts.append(chunk)
                yield {"type": "delta", "content": chunk}
        except Exception as exc:
            logger.debug("MCQ stream_chat 失败（第%s次）: %s", attempt + 1, exc)
        last_response = clean_mcq_output("".join(buffer_parts))
        try:
            parsed = parse_mcq_response(last_response, option_labels)
            if not validate_mcq_output(parsed, option_labels):
                raise MCQParseError(last_response, "validation failed")
            yield {"type": "stage", "content": {"name": "validate", "label": "校验答案", "progress": 95}}
            yield _serialize_answer_meta(parsed, last_response)
            yield {"type": "mcq_answer", "content": parsed.get("answer", "")}
            yield {"type": "done", "content": {"progress": 100}}
            return
        except MCQParseError as exc:
            last_error = exc
            yield {"type": "status", "content": "⚠️ 当前输出未通过校验，正在重试..."}
            if attempt == 0:
                yield {"type": "retry", "content": {"attempt": attempt + 1, "reason": str(exc)[:120]}}
            continue
    yield {"type": "stage", "content": {"name": "validate", "label": "校验答案", "progress": 95}}
    yield {"type": "status", "content": "⚠️ 解析失败，已降级为错误消息"}
    failure = _build_failure_result(mcq, sections, last_response, reason=last_error.reason if last_error else "unknown")
    yield {"type": "answer_meta", "content": {"answer": "", "formatted": failure["formatted"], "raw_text": last_response, "parse_failed": True}}
    yield {"type": "mcq_answer", "content": ""}
    yield {"type": "sources", "content": sections}
    yield {"type": "done", "content": {"progress": 100, "parse_failed": True}}
    return


async def solve_mcq(
    mcq: MCQQuestion,
    retriever,
    llm,
    doc_id: str = "",
    top_k: int = 10,
):
    result = await solve_mcq_with_elimination(mcq, retriever, llm, doc_id=doc_id, top_k=top_k)
    return result.get("answer", "")
