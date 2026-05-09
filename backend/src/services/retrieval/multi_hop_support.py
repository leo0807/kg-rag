from __future__ import annotations

import json
import logging
import re

from ..ai.llm import clean_llm_response
from ..ai.llm_service import get_llm_service
from ..answer_guard import validate_answer

logger = logging.getLogger(__name__)
DOC_ID_RE = re.compile(r"CPS\d{4}")

MAX_HOPS = 3


def build_decompose_prompt(question: str) -> str:
    return f"""你是中国商飞（COMAC）航空工艺专家。
将用户的复杂工艺问题分解为2-3个独立的子问题。

规则：
1. 每个子问题必须能通过检索工艺规范文档直接回答
2. 如果问题涉及多个规范（如CPS1000和CPS7251），
   每个规范单独生成一个子问题
3. 如果问题涉及跨规范比较，
   先分别查各规范，再生成对比子问题
4. 子问题必须包含具体的规范编号或工艺术语

示例：
原问题：CPS1000和CPS7251对密封圈的要求有什么不同？
分解为：
- CPS1000中对密封圈安装的具体要求是什么？
- CPS7251中对密封圈安装的具体要求是什么？

输出格式（只输出JSON，不要其他内容）：
{{"sub_questions": ["子问题1", "子问题2"]}}

问题：{question}"""


def extract_doc_ids(question: str) -> list[str]:
    return list(dict.fromkeys(DOC_ID_RE.findall(question or "")))


def extract_subject(question: str) -> str:
    text = re.sub(r"CPS\d{4}", "", question or "")
    for pattern in (
        r"对(.+?)(?:的要求|要求|有什么不同|有何不同|有何差异|有什么差异)",
        r"关于(.+?)(?:有什么不同|有何不同|要求|差异)",
        r"(.+?)(?:的要求|要求|有什么不同|有何不同|有何差异|有什么差异)",
    ):
        m = re.search(pattern, text)
        if m:
            subject = m.group(1).strip("，,。！？、和与 ")
            if subject:
                return subject
    return text.strip("，,。！？、和与 ")[:16] or "相关要求"


def build_doc_aware_sub_queries(question: str) -> list[str]:
    doc_ids = extract_doc_ids(question)
    if len(doc_ids) < 2:
        return []
    subject = extract_subject(question)
    return [f"{doc}中{subject}的具体要求是什么？" for doc in doc_ids[:2]]


def build_compare_hint(question: str) -> str:
    doc_ids = extract_doc_ids(question)
    subject = extract_subject(question)
    if len(doc_ids) >= 2:
        return (
            f"问题涉及多个规范：{', '.join(doc_ids[:2])}。"
            f"优先分别检索各规范中关于{subject}的定义、要求或步骤，再做对比。"
        )
    return ""


def _looks_like_bad_sub_queries(sub_queries: list[str], question: str) -> bool:
    if not sub_queries:
        return True
    if len(sub_queries) > 3:
        return True
    if any(len(q) < 6 for q in sub_queries):
        return True
    if question and all(q == question for q in sub_queries):
        return False
    if any(re.search(r"CPS\d{4}.*CPS\d{4}", q) for q in sub_queries):
        return True
    return False


def retrieve_for_subquery(sub_question: str, driver, top_k: int = 5) -> list[dict]:
    doc_ids = extract_doc_ids(sub_question)
    doc_id = doc_ids[0] if len(doc_ids) == 1 else ""
    from ...routers.query.core import do_retrieval

    sections, _ft_score_map, _expansion_info = do_retrieval(
        driver,
        sub_question,
        "parallel_rrf",
        top_k,
        doc_id=doc_id,
    )
    if not sections and doc_id:
        sections, _ft_score_map, _expansion_info = do_retrieval(
            driver,
            f"{doc_id} 相关要求",
            "parallel_rrf",
            top_k,
            doc_id=doc_id,
        )
    if not sections and doc_id:
        with driver.session() as session:
            rows = session.run(
                """
                MATCH (d:Document {doc_id: $doc_id})-[:HAS_SECTION]->(s:Section)
                WHERE s.content IS NOT NULL AND trim(s.content) <> ''
                RETURN s.chunk_id AS chunk_id,
                       s.doc_id   AS doc_id,
                       s.number   AS number,
                       s.title    AS title,
                       s.content  AS content,
                       s.page_idx AS page_idx,
                       s.bbox     AS bbox
                ORDER BY coalesce(s.page_idx, 999999), s.number
                LIMIT $top_k
                """,
                doc_id=doc_id,
                top_k=top_k,
            )
            sections = [dict(row) for row in rows]
    return sections


def build_multi_hop_context(retrieved: list[dict], limit: int = 6) -> tuple[str, list[dict]]:
    seen, unique = set(), []
    for r in retrieved:
        if r["chunk_id"] in seen:
            continue
        unique.append(r)
        seen.add(r["chunk_id"])

    context = "\n\n".join(
        f"[{r['doc_id']} §{r.get('number', '')} (第{r.get('page_idx', 0)+1}页)] {r['title']}\n{r.get('content', '')}"
        for r in unique[:limit]
    )
    return context, unique


def synthesize_answer(question: str, retrieved: list[dict], sub_queries: list[str]) -> tuple[str, list[dict], list[dict]]:
    if not retrieved:
        return "在知识库中未找到相关章节，请确认文件已入库。", [], []

    context, unique = build_multi_hop_context(retrieved)
    question_doc_ids = extract_doc_ids(question)
    if question_doc_ids:
        filtered = [r for r in unique if r.get("doc_id") in question_doc_ids]
        if filtered:
            unique = filtered
            context, unique = build_multi_hop_context(unique)
    compare_hint = build_compare_hint(question)
    prompt = build_synthesis_prompt(question, context, sub_queries)
    if compare_hint:
        prompt = f"{compare_hint}\n\n{prompt}"

    try:
        answer = get_llm_service().chat([{"role": "user", "content": prompt}], timeout=60)
    except Exception as e:
        logger.warning("多跳综合失败: %s", e)
        answer = f"根据多步检索，找到 {len(unique)} 个相关章节：\n\n{context[:2000]}"

    return validate_answer(clean_llm_response(answer), unique, question), unique, []


def synthesize_answer(question: str, retrieved: list[dict], sub_queries: list[str]) -> tuple[str, list[dict], list[dict]]:
    if not retrieved:
        return "在知识库中未找到相关章节，请确认文件已入库。", [], []

    seen, unique = set(), []
    for r in retrieved:
        if r["chunk_id"] in seen:
            continue
        unique.append(r)
        seen.add(r["chunk_id"])

    context = "\n\n".join(
        f"[{r['doc_id']} §{r.get('number', '')} (第{r.get('page_idx', 0)+1}页)] {r['title']}\n{r.get('content', '')}"
        for r in unique[:6]
    )
    compare_hint = build_compare_hint(question)
    prompt = build_synthesis_prompt(question, context, sub_queries)
    if compare_hint:
        prompt = f"{compare_hint}\n\n{prompt}"

    try:
        answer = get_llm_service().chat([{"role": "user", "content": prompt}], timeout=60)
    except Exception as e:
        logger.warning("多跳综合失败: %s", e)
        answer = f"根据多步检索，找到 {len(unique)} 个相关章节：\n\n{context[:2000]}"

    return validate_answer(clean_llm_response(answer), unique, question), unique, []


def parse_sub_queries(content: str, question: str) -> list[str]:
    try:
        payload = json.loads(content)
        if isinstance(payload, dict):
            sub_queries = payload.get("sub_questions", [])
            if isinstance(sub_queries, list):
                cleaned = [str(q).strip() for q in sub_queries if str(q).strip()]
                if cleaned:
                    return cleaned
    except Exception:
        pass
    lines = [line.strip(" -*•\t") for line in (content or "").splitlines()]
    cleaned = [line for line in lines if line]
    return cleaned or [question]


def build_synthesis_prompt(
    question: str,
    context: str,
    sub_queries: list[str],
) -> str:
    return f"""基于以下来自不同工艺规范的检索结果，
回答用户问题。

要求：
- 如果问题要求比较，必须明确列出每个规范的具体要求
- 引用时必须标注规范编号和章节号，格式：（CPS1000 §3.1）
- 不同规范的要求用分段或列表清晰区分
- 如果两个规范要求相同，明确说明“两者一致”
- 如果存在差异，用对比格式呈现

来源章节：
{context}

问题：{question}

子问题：
{chr(10).join(f"- {q}" for q in sub_queries)}"""


def fallback_parallel_answer(question: str, driver, top_k: int = 5) -> tuple[str, list[dict], list[dict]]:
    try:
        from ...routers.query.core import do_retrieval

        sections, _ft_scores, expansion_info = do_retrieval(
            driver,
            question,
            "parallel_rrf",
            top_k,
        )
        if not sections:
            raise ValueError("无结果")

        context = "\n\n".join(
            f"[{s['doc_id']} §{s.get('number', '')} (第{(s.get('page_idx', 0) or 0) + 1}页)] "
            f"{s.get('title', '')}\n{s.get('content', '')}"
            for s in sections[:6]
        )
        prompt = build_synthesis_prompt(question, context, [question])
        answer = get_llm_service().chat([{"role": "user", "content": prompt}], timeout=60)
        answer = validate_answer(clean_llm_response(answer), sections, question)
        steps = [
            {
                "hop": 0,
                "query": question,
                "found": len(sections),
                "titles": [s.get("title", "") for s in sections[:3]],
                "fallback": "parallel_rrf",
                "expansion": expansion_info,
            }
        ]
        return validate_answer(answer, sections, question), sections[:top_k], steps
    except Exception as e:
        logger.warning("multi_hop 降级到 parallel_rrf 失败: %s", e)
        return "在知识库中未找到相关章节，请确认文件已入库。", [], []
