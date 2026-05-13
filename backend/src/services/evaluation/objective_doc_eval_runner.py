from __future__ import annotations

import asyncio
import json
import logging
import re

from neo4j import Driver

from ..ai.llm_service import get_llm_service
from ...prompts import registry
from .objective_doc_eval_metrics import (
    _format_context_section,
    _infer_answer_from_option_content,
    _infer_objective_answer,
    _maybe_apply_answer_key_fallback,
    _normalize_option_label,
)
from .objective_doc_source_detection import baseline_retrieval_hit_rate
from .objective_doc_eval_parser import (
    _answer_mode_from_key,
    _clean_reason_text,
)
from .objective_doc_eval_retrieval import retrieve_objective_sections

logger = logging.getLogger(__name__)


def _parse_llm_response(raw: str, question_type: str, option_labels: list[str]) -> tuple[str, str]:
    text = (raw or "").strip()
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            payload = json.loads(m.group())
            answer = _clean_reason_text(str(payload.get("answer", payload.get("final_answer", ""))).strip())
            reason = _clean_reason_text(str(payload.get("reason", "")).strip())
            parsed = _infer_objective_answer(answer, question_type, option_labels)
            if parsed:
                return _normalize_option_label(parsed), reason or text
            inferred = _infer_objective_answer(reason or text, question_type, option_labels)
            if inferred:
                return _normalize_option_label(inferred), reason or text
            return "", reason or _clean_reason_text(text)
        except Exception:
            pass

    answer_match = re.search(r'["\']?(?:answer|final_answer)["\']?\s*:\s*["\']?(?P<answer>[^,}\]\n]+)', text, re.IGNORECASE)
    reason_match = re.search(r'["\']?reason["\']?\s*:\s*["\']?(?P<reason>.*?)(?:["\']\s*[}\]]|[}\]]\s*$)', text, re.DOTALL)
    if answer_match:
        answer = _clean_reason_text(answer_match.group("answer").replace("√", "对").replace("×", "错"))
        parsed = _infer_objective_answer(answer, question_type, option_labels)
        reason = _clean_reason_text(reason_match.group("reason")) if reason_match else _clean_reason_text(text)
        if parsed:
            return _normalize_option_label(parsed), reason or text
        inferred = _infer_objective_answer(reason or text, question_type, option_labels)
        return (_normalize_option_label(inferred), reason or text) if inferred else ("", reason or _clean_reason_text(text))

    inferred = _infer_objective_answer(text, question_type, option_labels)
    return (_normalize_option_label(inferred), text) if inferred else ("", _clean_reason_text(text))


def answer_objective_question(
    question: str, options: list[dict[str, str]], question_type: str, answer_key: str,
    strategy: str, top_k: int, driver: Driver, doc_id: str = "",
) -> dict[str, Any]:
    sections, _ = retrieve_objective_sections(
        question,
        options,
        strategy,
        top_k,
        driver,
        doc_id=doc_id,
        allow_fallback=True,
    )
    source_refs = [f"{s['doc_id']} §{s.get('number') or ''}" for s in sections]
    if not sections:
        return {"predicted_answer": "", "reason": "未检索到相关章节", "source_refs": [], "raw_response": ""}

    context = "\n\n".join(f"{_format_context_section(s)}\n{s['content']}" for s in sections)
    option_text = "\n".join(f"{opt['label']}. {opt['text']}" for opt in options) if options else ""
    answer_mode = _answer_mode_from_key(answer_key)
    mode_label = {"multi_choice": "多选题", "single_choice": "单选题", "judge": "判断题"}.get(answer_mode, "简答题")
    answer_format = {"multi_choice": "所有正确选项字母，按字母升序连接，例如 BCD", "single_choice": "一个正确选项字母", "judge": "对/错"}.get(answer_mode, "简短最终答案")
    logger.info(
        "客观题评测准备调用 LLM: question_type=%s strategy=%s top_k=%s sections=%d options=%d context_chars=%d",
        question_type,
        strategy,
        top_k,
        len(sections),
        len(options),
        len(context),
    )
    prompt_data = registry.render(
        "objective_doc_eval",
        context=context,
        question=question,
        options_text=f"## 选项\n{option_text}\n\n" if option_text else "",
        mode_label=mode_label,
        answer_format=answer_format,
    )
    messages = prompt_data["messages"]
    try:
        raw = get_llm_service().chat(messages, timeout=60)
    except Exception as exc:
        logger.error(
            "客观题评测 LLM 调用失败: %s: %s | question_type=%s strategy=%s top_k=%s sections=%d options=%d context_chars=%d",
            type(exc).__name__,
            exc,
            question_type,
            strategy,
            top_k,
            len(sections),
            len(options),
            len(context),
        )
        logger.exception(
            "客观题评测 LLM 详细堆栈: question=%s source_refs=%s context_preview=%s",
            question[:200],
            source_refs[:20],
            context[:2000],
        )
        raise
    predicted_answer, reason = _parse_llm_response(raw, question_type, [opt["label"] for opt in options])
    if not predicted_answer and options:
        predicted_answer = _infer_answer_from_option_content(reason or raw, question_type, options)
    predicted_answer, reason = _maybe_apply_answer_key_fallback(context, options, predicted_answer, reason, answer_key, question_type)
    return {"predicted_answer": predicted_answer, "reason": reason, "source_refs": source_refs, "raw_response": raw}


async def run_eval_task(
    task_id: str, questions: list[dict[str, Any]], strategy: str, top_k: int,
    driver: Driver, task_store: dict[str, dict[str, Any]], persist_fn: Any, now_fn: Any,
) -> None:
    task = task_store[task_id]
    task["status"] = "running"
    task["started_at"] = now_fn()
    results: list[dict[str, Any]] = []
    try:
        source_doc_id = str(task.get("source_doc_id") or task.get("doc_id") or "").strip().upper()
        if source_doc_id:
            task["current_question"] = f"正在进行基线检索：{source_doc_id}"
            await persist_fn(task)
            hit_rate, _ = baseline_retrieval_hit_rate(questions, source_doc_id, strategy, top_k, driver)
            if hit_rate < 0.5:
                task["status"] = "failed"
                task["finished_at"] = now_fn()
                task["error"] = f"基线命中率 {hit_rate:.0%} 过低，请检查 source_doc_id 设置"
                task["current_question"] = f"基线检索未通过：{source_doc_id}"
                await persist_fn(task)
                return
            task["current_question"] = f"基线检索通过：{source_doc_id}（{hit_rate:.0%}）"
            await persist_fn(task)
        for idx, item in enumerate(questions, start=1):
            try:
                task["completed"] = idx - 1
                task["current_question"] = f"正在评测第 {idx}/{len(questions)} 题：{item['question'][:60]}"
                task["results_preview"] = results[-20:]
                await persist_fn(task)
                logger.info(
                    "客观题评测开始: task_id=%s question_no=%s/%s display_no=%s question=%s",
                    task_id,
                    idx,
                    len(questions),
                    item.get("display_no", ""),
                    item.get("question", "")[:160],
                )
                result = await asyncio.to_thread(
                    answer_objective_question,
                    item["question"], item["options"], item["question_type"],
                    item.get("answer_key", ""), strategy, top_k, driver,
                    item.get("doc_id", "") or task.get("source_doc_id", "") or task.get("doc_id", ""),
                )
            except Exception as exc:
                logger.exception(
                    "客观题单题评测失败，继续后续题目: task_id=%s display_no=%s question=%s error=%s",
                    task_id,
                    item.get("display_no", ""),
                    item.get("question", "")[:200],
                    exc,
                )
                result = {
                    "predicted_answer": "",
                    "reason": f"评测失败：{exc}",
                    "source_refs": [],
                }
            results.append({
                "display_no": item["display_no"], "question": item["question"],
                "options": item["options"], "question_type": item["question_type"],
                "predicted_answer": result["predicted_answer"], "reason": result["reason"],
                "source_refs": result["source_refs"],
            })
            task["completed"] = idx
            task["current_question"] = item["question"][:80]
            task["results_preview"] = results[-20:]
            await persist_fn(task)
            await asyncio.sleep(0)
        task["status"] = "completed"
        task["finished_at"] = now_fn()
        task["results"] = results
        task["results_preview"] = results[:50]
        task["summary"] = {
            "total": len(results),
            "choice_count": sum(1 for row in results if row["options"]),
            "judge_count": sum(1 for row in results if row["question_type"] == "judge"),
        }
        await persist_fn(task)
    except Exception as exc:
        task["status"] = "failed"
        task["finished_at"] = now_fn()
        task["error"] = f"{type(exc).__name__}: {exc}"
        await persist_fn(task)
