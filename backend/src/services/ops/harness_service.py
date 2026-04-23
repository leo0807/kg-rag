from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from neo4j import Driver

logger = logging.getLogger(__name__)

DO_RETRIEVAL: Any | None = None
ANSWER_GENERATOR: Any | None = None

_STOP_TERMS = {
    "什么", "哪些", "哪里", "一下", "一下子", "关于", "相关", "要求", "规定", "如何",
    "怎么", "这个", "那个", "以及", "一下", "是否", "可以", "需要", "查看", "检索",
    "查询", "文档", "章节", "内容", "主要", "有关", "一下", "给我", "告诉我",
}


def _get_do_retrieval():
    global DO_RETRIEVAL
    if callable(DO_RETRIEVAL):
        return DO_RETRIEVAL

    from ...routers.query.core import do_retrieval

    DO_RETRIEVAL = do_retrieval
    return do_retrieval


def _get_answer_generator():
    global ANSWER_GENERATOR
    if callable(ANSWER_GENERATOR):
        return ANSWER_GENERATOR

    from ..llm import generate_answer_with_usage

    ANSWER_GENERATOR = generate_answer_with_usage
    return generate_answer_with_usage


def recommend_strategy(question: str) -> tuple[str, str]:
    q = (question or "").lower()

    if any(kw in q for kw in ["对比", "比较", "区别", "不同", "差异"]):
        return "parallel", "对比型问题优先走并行检索"
    if any(kw in q for kw in ["引用", "参照", "依据", "来源", "关联章节", "引用文件"]):
        return "graph_augmented", "引用/依据问题先走图谱增强检索，便于稳定串联引用链"
    if any(kw in q for kw in ["图纸", "工程图", "示意图", "装配图", "件号", "标注"]):
        return "graph_augmented", "图纸问题需要章节与图片联合检索"
    if any(kw in q for kw in ["力矩", "温度", "压力", "公差", "参数", "数值", "范围", "极限"]):
        return "graph_augmented", "参数/约束问题优先走图谱增强检索"
    if any(kw in q for kw in ["如何", "步骤", "流程", "怎么", "操作", "程序", "顺序"]):
        return "graph_augmented", "流程型问题优先走图谱增强检索"
    return "parallel", "默认走通用并行检索"


def extract_query_terms(question: str) -> list[str]:
    raw_terms = re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9._-]{2,}", question or "")
    terms: list[str] = []
    seen: set[str] = set()
    for item in raw_terms:
        term = item.strip().lower()
        if not term or term in _STOP_TERMS or term.isdigit():
            continue
        if term not in seen:
            seen.add(term)
            terms.append(term)
    return terms[:12]


def build_execution_plan(question: str, *, doc_id: str = "", strategy: str = "") -> dict[str, Any]:
    resolved_strategy, reason = (strategy, "使用调用方指定检索策略") if strategy else recommend_strategy(question)
    if resolved_strategy == "multi_hop":
        resolved_strategy = "graph_augmented"
        reason = "统一 harness MVP 暂以图谱增强检索承接多跳意图"
    intents: list[str] = ["sections"]
    lower_q = (question or "").lower()

    if any(kw in lower_q for kw in ["图纸", "工程图", "示意图", "装配图", "件号", "标注"]):
        intents.append("drawings")
    if any(kw in lower_q for kw in ["引用", "参照", "依据", "来源", "引用文件"]):
        intents.append("references")
    if any(kw in lower_q for kw in ["范围", "参数", "公差", "力矩", "温度", "压力", "极限"]):
        intents.append("constraints")

    steps = [
        {"tool": "section_retrieval", "description": f"使用 {resolved_strategy} 召回章节证据"},
    ]
    if "drawings" in intents:
        steps.append({"tool": "drawing_search", "description": "补充工程图纸/图片摘要证据"})
    if "references" in intents:
        steps.append({"tool": "reference_trace", "description": "保留引用关系意图，复用图谱链路"})
    steps.append({"tool": "answer_synthesis", "description": "汇总章节与图片证据生成回答"})

    return {
        "strategy": resolved_strategy,
        "reason": reason,
        "doc_id": doc_id,
        "intents": intents,
        "steps": steps,
    }


def _document_images_match() -> str:
    return """
        MATCH (d:Document)
        WHERE ($doc_id = '' OR d.name = $doc_id)
        OPTIONAL MATCH (d)-[:HAS_SECTION]->(:Section)-[:HAS_IMAGE]->(section_img:Image)
        WITH d, collect(DISTINCT section_img) AS section_imgs
        OPTIONAL MATCH (d)-[:HAS_IMAGE]->(doc_img:Image)
        WITH d, section_imgs + collect(DISTINCT doc_img) AS all_imgs
        UNWIND all_imgs AS img
        WITH DISTINCT d, img
        WHERE img IS NOT NULL
    """


def _query_image_rows(
    driver: Driver,
    *,
    terms: list[str],
    doc_id: str,
    limit: int,
    drawing_only: bool,
) -> list[dict[str, Any]]:
    with driver.session() as session:
        result = session.run(
            _document_images_match()
            + """
            WITH
                d,
                img,
                toLower(
                    coalesce(img.caption, '')
                    + ' ' + coalesce(img.description, '')
                    + ' ' + coalesce(img.drawing_summary, '')
                    + ' ' + coalesce(img.part_numbers, '')
                    + ' ' + coalesce(img.annotations, '')
                    + ' ' + coalesce(img.assembly_relations, '')
                ) AS haystack
            WITH
                d,
                img,
                size([term IN $terms WHERE haystack CONTAINS term]) AS keyword_hits
            WHERE
                ($drawing_only = false OR coalesce(img.is_drawing, false))
                AND (
                    size($terms) = 0
                    OR keyword_hits > 0
                    OR ($drawing_only = true AND coalesce(img.is_drawing, false))
                )
            OPTIONAL MATCH (s:Section)-[:HAS_IMAGE]->(img)
            RETURN
                img.image_id AS image_id,
                d.name AS doc_id,
                img.caption AS caption,
                img.description AS description,
                img.drawing_summary AS drawing_summary,
                img.is_drawing AS is_drawing,
                img.minio_path AS minio_path,
                coalesce(img.page_num, img.page, 0) AS page,
                head(collect(DISTINCT s.number)) AS section_number,
                head(collect(DISTINCT s.title)) AS section_title,
                keyword_hits
            ORDER BY keyword_hits DESC, coalesce(img.is_drawing, false) DESC, coalesce(img.page_num, img.page, 0), img.image_id
            LIMIT $limit
            """,
            terms=terms,
            doc_id=doc_id,
            limit=max(limit, 1),
            drawing_only=drawing_only,
        )
        return [dict(row) for row in result]


def search_image_evidence(
    driver: Driver,
    *,
    question: str,
    doc_id: str = "",
    limit: int = 6,
    drawing_only: bool = False,
) -> list[dict[str, Any]]:
    terms = extract_query_terms(question)
    if not terms and not drawing_only:
        return []
    rows = _query_image_rows(
        driver,
        terms=terms,
        doc_id=doc_id,
        limit=limit * 3,
        drawing_only=drawing_only,
    )

    images: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for row in rows:
        image_id = str(row.get("image_id") or "").strip()
        if not image_id or image_id in seen_ids:
            continue
        seen_ids.add(image_id)
        summary = (
            row.get("drawing_summary")
            or row.get("caption")
            or row.get("description")
            or ""
        ).strip()
        images.append(
            {
                "image_id": image_id,
                "doc_id": row.get("doc_id") or "",
                "summary": summary,
                "caption": row.get("caption") or "",
                "description": row.get("description") or "",
                "is_drawing": bool(row.get("is_drawing")),
                "section_number": row.get("section_number") or "",
                "section_title": row.get("section_title") or "",
                "page": row.get("page"),
                "keyword_hits": int(row.get("keyword_hits") or 0),
                "url": f"/api/images/{image_id}" if row.get("minio_path") else None,
            },
        )
        if len(images) >= limit:
            break
    return images


def _build_context(sections: list[dict[str, Any]], images: list[dict[str, Any]]) -> str:
    blocks: list[str] = []
    for section in sections[:6]:
        blocks.append(
            f"[章节 {section.get('doc_id', '')} §{section.get('number', '')}] "
            f"{section.get('title', '')}\n{section.get('content', '')}"
        )
    for image in images[:4]:
        summary = image.get("summary") or image.get("caption") or ""
        if not summary:
            continue
        blocks.append(
            f"[图片 {image.get('doc_id', '')} #{image.get('image_id', '')}] "
            f"{summary}"
        )
    return "\n\n".join(blocks)


def _build_answer(question: str, sections: list[dict[str, Any]], images: list[dict[str, Any]]) -> str:
    context = _build_context(sections, images)
    if not context:
        return "当前没有召回到可用于回答的章节或图片证据。"

    try:
        generate_answer = _get_answer_generator()
        answer, _usage = generate_answer(
            question=question,
            context=context,
            history=[],
        )
        return answer
    except Exception as exc:
        logger.warning("harness 回答生成失败，回退摘要模式: %s", exc)
        return context[:2000]


def run_harness_query(
    driver: Driver,
    *,
    question: str,
    top_k: int = 5,
    doc_id: str = "",
    strategy: str = "",
) -> dict[str, Any]:
    plan = build_execution_plan(question, doc_id=doc_id, strategy=strategy)
    do_retrieval = _get_do_retrieval()
    sections, ft_score_map = do_retrieval(
        driver,
        question,
        plan["strategy"],
        top_k,
        False,
        0.5,
        doc_id,
    )
    section_sources = [
        {
            "chunk_id": item["chunk_id"],
            "doc_id": item["doc_id"],
            "number": item.get("number") or "",
            "title": item.get("title") or "",
            "page_idx": item.get("page_idx"),
            "bbox": item.get("bbox"),
            "source_type": item.get("source_type", []),
            "retrieval_trace": item.get("retrieval_trace", []),
            "score": round(item.get("rerank_score") or ft_score_map.get(item["chunk_id"], 0.0), 4),
            "content": item.get("content") or "",
        }
        for item in sections
    ]

    drawing_only = "drawings" in plan["intents"]
    image_sources = search_image_evidence(
        driver,
        question=question,
        doc_id=doc_id,
        limit=min(max(top_k, 3), 8),
        drawing_only=drawing_only,
    )
    answer = _build_answer(question, sections, image_sources)

    retrieval_trace_counts: dict[str, int] = {}
    for section in section_sources:
        for trace in section.get("retrieval_trace", []):
            retrieval_trace_counts[trace] = retrieval_trace_counts.get(trace, 0) + 1

    runtime = {
        "doc_id": doc_id,
        "strategy": plan["strategy"],
        "top_k": top_k,
        "section_hits": len(section_sources),
        "image_hits": len(image_sources),
        "drawing_only": drawing_only,
        "retrieval_trace_counts": retrieval_trace_counts,
        "warnings": [] if section_sources or image_sources else ["未命中任何章节或图片证据"],
    }

    return {
        "question": question,
        "answer": answer,
        "plan": plan,
        "runtime": runtime,
        "section_sources": section_sources,
        "image_sources": image_sources,
    }


def builtin_retrieval_cases_path() -> Path:
    return Path(__file__).resolve().parents[3] / "eval" / "retrieval_cases.jsonl"
