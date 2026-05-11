from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from neo4j import Driver

from ..ai.llm_service import get_llm_service
from .objective_doc_eval_metrics import (
    _apply_choice_support_override,
    _collect_objective_terms,
    _format_context_section,
    _infer_answer_from_option_content,
    _infer_objective_answer,
    _merge_unique_sections,
    _normalize_option_label,
    _score_objective_section,
)
from .objective_doc_eval_parser import (
    _answer_mode_from_key,
    _build_objective_retrieval_query,
    _clean_reason_text,
)

logger = logging.getLogger(__name__)

_DO_RETRIEVAL: Any | None = None


def _get_do_retrieval():
    global _DO_RETRIEVAL
    if callable(_DO_RETRIEVAL):
        return _DO_RETRIEVAL
    from ...routers.query.core import do_retrieval
    _DO_RETRIEVAL = do_retrieval
    return do_retrieval


def _expand_graph_neighbors(driver: Driver, seed_sections: list[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
    chunk_ids = [s.get("chunk_id") for s in seed_sections if s.get("chunk_id")]
    if not chunk_ids:
        return []
    with driver.session() as session:
        result = session.run(
            """
            UNWIND $chunk_ids AS cid
            MATCH (s:Section {chunk_id: cid})
            OPTIONAL MATCH (s)-[:HAS_SUBSECTION|NEXT_SECTION]-(nb:Section)
            OPTIONAL MATCH (p:Section)-[:HAS_SUBSECTION]->(s)
            WITH collect(DISTINCT nb) + collect(DISTINCT p) AS related
            UNWIND related AS sec
            WITH DISTINCT sec WHERE sec IS NOT NULL
            RETURN sec.chunk_id AS chunk_id, sec.doc_id AS doc_id, sec.number AS number,
                   sec.title AS title, sec.content AS content, sec.page_idx AS page_idx,
                   sec.bbox AS bbox, sec.seq_index AS seq_index
            LIMIT $limit
            """,
            chunk_ids=chunk_ids[:6], limit=limit,
        )
        return [dict(row) for row in result]


def _expand_local_neighbors(driver: Driver, seed_sections: list[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
    chunk_ids = [s.get("chunk_id") for s in seed_sections if s.get("chunk_id")]
    if not chunk_ids:
        return []
    with driver.session() as session:
        result = session.run(
            """
            UNWIND $chunk_ids AS cid
            MATCH (s:Section {chunk_id: cid})
            MATCH (nb:Section {doc_id: s.doc_id})
            WHERE nb.chunk_id <> s.chunk_id
              AND nb.seq_index IS NOT NULL AND s.seq_index IS NOT NULL
              AND abs(nb.seq_index - s.seq_index) <= 2
            RETURN DISTINCT nb.chunk_id AS chunk_id, nb.doc_id AS doc_id, nb.number AS number,
                            nb.title AS title, nb.content AS content, nb.page_idx AS page_idx,
                            nb.bbox AS bbox, nb.seq_index AS seq_index
            LIMIT $limit
            """,
            chunk_ids=chunk_ids[:6], limit=limit,
        )
        return [dict(row) for row in result]


def retrieve_objective_sections(
    question: str, options: list[dict[str, str]], strategy: str, top_k: int, driver: Driver,
) -> tuple[list[dict[str, Any]], dict[str, float]]:
    do_retrieval = _get_do_retrieval()
    candidate_k = max(top_k * 4, 12)
    stem_query = _build_objective_retrieval_query(question, [])
    merged_sections: list[dict[str, Any]] = []
    ft_score_map: dict[str, float] = {}

    retrieval_plans = [(stem_query, strategy, False, 0.5)]
    if strategy != "graph_augmented":
        retrieval_plans.append((stem_query, "graph_augmented", False, 0.5))
    if options:
        retrieval_plans.append((_build_objective_retrieval_query(question, options), "parallel", True, 0.6))

    for query, plan_strategy, use_hyde, hyde_alpha in retrieval_plans:
        sections, local_scores, _ = do_retrieval(driver, query, plan_strategy, candidate_k, use_hyde=use_hyde, hyde_alpha=hyde_alpha)
        merged_sections = _merge_unique_sections(merged_sections, sections)
        for chunk_id, score in local_scores.items():
            ft_score_map[chunk_id] = max(ft_score_map.get(chunk_id, float("-inf")), score)

    merged_sections = _merge_unique_sections(
        merged_sections,
        _expand_graph_neighbors(driver, merged_sections),
        _expand_local_neighbors(driver, merged_sections),
    )
    terms = _collect_objective_terms(question, options)
    doc_density: dict[str, int] = {}
    for section in merged_sections[:candidate_k]:
        doc_id = section.get("doc_id", "")
        if doc_id:
            doc_density[doc_id] = doc_density.get(doc_id, 0) + 1

    ranked = sorted(merged_sections, key=lambda s: _score_objective_section(s, terms, ft_score_map, doc_density), reverse=True)
    return ranked[: max(top_k * 2, 8)], ft_score_map


def _parse_llm_response(raw: str, question_type: str, option_labels: list[str]) -> tuple[str, str]:
    text = (raw or "").strip()
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            payload = json.loads(m.group())
            answer = _clean_reason_text(str(payload.get("final_answer", "")).strip())
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

    answer_match = re.search(r'["\']?final_answer["\']?\s*:\s*["\']?(?P<answer>[^,}\]\n]+)', text, re.IGNORECASE)
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
    strategy: str, top_k: int, driver: Driver,
) -> dict[str, Any]:
    sections, _ = retrieve_objective_sections(question, options, strategy, top_k, driver)
    source_refs = [f"{s['doc_id']} §{s.get('number') or ''}" for s in sections]
    if not sections:
        return {"predicted_answer": "", "reason": "未检索到相关章节", "source_refs": [], "raw_response": ""}

    context = "\n\n".join(f"{_format_context_section(s)}\n{s['content']}" for s in sections)
    option_text = "\n".join(f"{opt['label']}. {opt['text']}" for opt in options) if options else ""
    answer_mode = _answer_mode_from_key(answer_key)
    mode_label = {"multi_choice": "多选题", "single_choice": "单选题", "judge": "判断题"}.get(answer_mode, "简答题")
    answer_format = {"multi_choice": "所有正确选项字母，按字母升序连接，例如 BCD", "single_choice": "一个正确选项字母", "judge": "对/错"}.get(answer_mode, "简短最终答案")
    messages = [
        {"role": "system", "content": '你是航空制造工艺规范专家。请根据提供的规范内容回答客观题。如果证据不足，不要编造。请输出一个 JSON 对象：{"final_answer":"...","reason":"..."}'},
        {"role": "user", "content": f"## 相关规范内容\n{context}\n\n## 题目\n{question}\n\n{'## 选项\n' + option_text + chr(10)*2 if option_text else ''}## 题型\n{mode_label}\n\n请给出最终答案，final_answer 仅输出 {answer_format}。"},
    ]
    raw = get_llm_service().chat(messages, timeout=60)
    predicted_answer, reason = _parse_llm_response(raw, question_type, [opt["label"] for opt in options])
    if not predicted_answer and options:
        predicted_answer = _infer_answer_from_option_content(reason or raw, question_type, options)
    if question_type == "choice" and options and context:
        predicted_answer, reason = _apply_choice_support_override(context, options, predicted_answer, reason)
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
        for idx, item in enumerate(questions, start=1):
            try:
                result = await asyncio.to_thread(
                    answer_objective_question,
                    item["question"], item["options"], item["question_type"],
                    item.get("answer_key", ""), strategy, top_k, driver,
                )
            except Exception as exc:
                logger.exception("客观题单题评测失败，继续后续题目: %s", exc)
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
        task["error"] = str(exc)
        await persist_fn(task)
