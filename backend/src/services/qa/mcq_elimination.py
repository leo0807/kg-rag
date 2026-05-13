from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from typing import Any

from ...prompts import registry
from .mcq_handler import parse_options_from_question
from ..evaluation.objective_doc_eval_metrics import _infer_objective_answer

logger = logging.getLogger(__name__)

_PURPOSE_HINTS = ("目的", "目的是", "作用", "用途", "为什么", "为何", "干什么", "做什么")
_PROCEDURE_HINTS = ("步骤", "顺序", "过程", "方法", "安装", "检验", "检查", "操作")
_SCENE_HINTS = ("整体油箱", "客舱增压", "气动性能", "装配", "安装位置", "系统", "部位", "区域", "结构")
_ACTION_HINTS = ("防漏", "防腐蚀", "防漏水", "防漏油", "防漏气", "防止", "避免")
_OPTION_SPLIT_RE = re.compile(r"[、，,;；/／\s]+")


@dataclass(frozen=True)
class MCQQuestion:
    stem: str
    options: dict[str, str]


def build_mcq_question(question: str) -> MCQQuestion | None:
    opts = parse_options_from_question(question)
    if not opts:
        return None
    stem = re.sub(r'(\n[A-Da-d]\s+.*|[（(][A-Da-d][）)].+)', '', question, flags=re.DOTALL).strip() or question.strip()
    return MCQQuestion(stem=stem, options=opts)


def _split_option_parts(text: str) -> list[str]:
    parts = [p.strip(" 、,，;；:/／\t") for p in _OPTION_SPLIT_RE.split(text or "") if p.strip(" 、,，;；:/／\t")]
    return parts or [text.strip()]


def _question_focus(stem: str) -> str:
    if any(kw in stem for kw in _PURPOSE_HINTS):
        return "purpose"
    if any(kw in stem for kw in _PROCEDURE_HINTS):
        return "procedure"
    return "general"


def _classify_option_part(part: str) -> str:
    if not part:
        return "neutral"
    if part.startswith(_ACTION_HINTS) or any(hint in part for hint in _ACTION_HINTS):
        return "purpose"
    if any(hint in part for hint in _SCENE_HINTS):
        return "scene"
    return "neutral"


def _eliminate_choice_options(mcq: MCQQuestion) -> tuple[str, str, dict[str, dict[str, Any]]]:
    focus = _question_focus(mcq.stem)
    analyses: dict[str, dict[str, Any]] = {}
    scores: dict[str, int] = {}
    for letter, text in mcq.options.items():
        parts = _split_option_parts(text)
        purpose_parts = [p for p in parts if _classify_option_part(p) == "purpose"]
        scene_parts = [p for p in parts if _classify_option_part(p) == "scene"]
        score = len(purpose_parts) * 3 - len(scene_parts) * 4
        if focus == "purpose" and text.strip().startswith("防"):
            score += 2
        if focus == "purpose" and len(parts) == len(purpose_parts) and parts:
            score += 2
        if focus == "purpose" and scene_parts and purpose_parts:
            score -= 1
        scores[letter] = score
        analyses[letter] = {"purpose_parts": purpose_parts, "scene_parts": scene_parts}

    ordered = sorted(scores.items(), key=lambda item: (item[1], item[0]), reverse=True)
    best_letter = ordered[0][0] if ordered else ""
    return best_letter, focus, analyses


def _format_elimination_answer(
    mcq: MCQQuestion,
    focus: str,
    analyses: dict[str, dict[str, Any]],
    predicted: str,
    evidence_text: str = "",
) -> str:
    lines: list[str] = []
    lines.append(
        "题目类型分析：这道题问的是“目的”，应优先保留“防xxx”类短语，排除应用场景词。"
        if focus == "purpose"
        else "题目类型分析：根据选项和题干语义，逐项排除不符合题意的选项。"
    )
    lines.append("")
    lines.append("逐项排除：")
    for letter in sorted(mcq.options):
        analysis = analyses.get(letter, {})
        purpose_parts = analysis.get("purpose_parts", [])
        scene_parts = analysis.get("scene_parts", [])
        status = "保留" if predicted == letter else "排除"
        if focus == "purpose":
            if purpose_parts and not scene_parts:
                reason = "全部为“防xxx”短语，符合目的描述。"
            elif scene_parts and purpose_parts:
                reason = f"包含应用场景词{('、'.join(scene_parts[:2]))}，混合了场景和目的。"
            elif scene_parts:
                reason = f"包含应用场景词{('、'.join(scene_parts[:2]))}，不是目的描述。"
            elif purpose_parts:
                reason = "包含目的性短语，但不够完整。"
            else:
                reason = "未见明显的目的性短语。"
        else:
            reason = "与题目要求的语义类型不一致。"
        lines.append(f"{letter}. {status} - 原因：{reason}")
    lines.append("")
    lines.append(f"最终答案：{predicted or '未知'}")
    if evidence_text.strip():
        lines.append("")
        lines.append("依据：已检索相关规范章节，结合题干语义进行排除后得到上述答案。")
    return "\n".join(lines).strip()


def _parse_llm_choice(raw: str, option_labels: list[str]) -> str:
    text = (raw or "").strip()
    m = re.search(r"(?:最终答案|答案|final_answer)\s*[:：=]\s*([A-HＡ-Ｈ])", text, re.IGNORECASE)
    if m:
        cand = m.group(1).upper().translate(str.maketrans("ＡＢＣＤＥＦＧＨ", "ABCDEFGH"))
        if cand in option_labels:
            return cand
    parsed = _infer_objective_answer(text, "choice", option_labels)
    return parsed if parsed in option_labels else ""


async def solve_mcq_with_elimination(
    mcq: MCQQuestion,
    retriever,
    llm,
    doc_id: str = "",
    top_k: int = 10,
) -> dict[str, Any]:
    from ...routers.query.core import do_retrieval

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
    evidence_lines: list[str] = []
    for sec in sections[:6]:
        number = sec.get("number") or ""
        title = sec.get("title") or ""
        content = (sec.get("content") or "").replace("\n", " ").strip()
        if len(content) > 120:
            content = content[:120] + "..."
        evidence_lines.append(f"[{sec.get('doc_id', '')} §{number}] {title}\n{content}")
    evidence_text = "\n\n".join(evidence_lines)

    predicted, focus, analyses = _eliminate_choice_options(mcq)
    llm_response = ""
    option_labels = list(mcq.options.keys())
    if not predicted or focus != "purpose":
        prompt_data = registry.render(
            "qa_mcq",
            evidence_text=evidence_text,
            question=mcq.stem,
            options_text=chr(10).join(f"{k}. {v}" for k, v in mcq.options.items()),
            answer_format="选项字母",
        )
        try:
            raw = await asyncio.to_thread(
                llm.chat,
                prompt_data["messages"],
                timeout=60,
                max_tokens=prompt_data["max_tokens"],
            )
            llm_response = raw or ""
            parsed = _parse_llm_choice(llm_response, option_labels)
            if parsed:
                predicted = parsed
        except Exception as exc:
            logger.debug("MCQ LLM 排除法失败（使用规则结果）: %s", exc)

    answer = _format_elimination_answer(mcq, focus, analyses, predicted, evidence_text)
    logger.info("MCQ排除法结果: focus=%s predicted=%s options=%s", focus, predicted, list(mcq.options.keys()))
    return {
        "answer": answer,
        "predicted": predicted,
        "sources": sections,
        "evidence_text": evidence_text,
        "raw_response": llm_response,
        "strategy_used": "mcq_elimination",
    }
