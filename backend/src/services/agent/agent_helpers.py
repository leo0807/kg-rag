from __future__ import annotations

import re


def is_compare_question(question: str) -> bool:
    text = question or ""
    compare_words = ("不同", "差异", "区别", "比较", "有什么不同", "对比")
    return len(re.findall(r"CPS\d{3,4}", text.upper())) >= 2 and any(
        word in text for word in compare_words
    )


def build_compare_plan(question: str) -> list[dict]:
    doc_ids = re.findall(r"CPS\d{3,4}", question.upper())
    if len(doc_ids) < 2:
        return []
    topic = re.sub(r"CPS\d{3,4}", "", question)
    topic = re.sub(r"[和与及,，。？?比较不同差异区别有什么对比]\s*", " ", topic)
    topic = re.sub(r"\s+", " ", topic).strip() or "相关要求"
    return [
        {"name": "search_sections", "input": {"query": topic, "doc_id": doc_ids[0], "top_k": 5}},
        {"name": "search_sections", "input": {"query": topic, "doc_id": doc_ids[1], "top_k": 5}},
        {
            "name": "compare_documents",
            "input": {
                "doc_id_a": doc_ids[0],
                "doc_id_b": doc_ids[1],
                "topic": topic,
            },
        },
    ]


def collect_tool_outputs(tool_name: str, tool_result: dict) -> tuple[list[dict], list[dict]]:
    sections: list[dict] = []
    images: list[dict] = []
    if not isinstance(tool_result, dict):
        return sections, images

    direct_sections = tool_result.get("sections")
    if isinstance(direct_sections, list):
        sections.extend([item for item in direct_sections if isinstance(item, dict)])

    direct_images = tool_result.get("images")
    if isinstance(direct_images, list):
        images.extend([item for item in direct_images if isinstance(item, dict)])

    if tool_name == "compare_documents":
        for value in tool_result.values():
            if isinstance(value, dict):
                nested_sections = value.get("sections", [])
                nested_images = value.get("images", [])
                if isinstance(nested_sections, list):
                    sections.extend([item for item in nested_sections if isinstance(item, dict)])
                if isinstance(nested_images, list):
                    images.extend([item for item in nested_images if isinstance(item, dict)])
    return dedupe_sections(sections), dedupe_images(images)


def dedupe_sections(sections: list[dict]) -> list[dict]:
    seen: set[str] = set()
    deduped: list[dict] = []
    for item in sections:
        key = str(item.get("chunk_id") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def dedupe_images(images: list[dict]) -> list[dict]:
    seen: set[str] = set()
    deduped: list[dict] = []
    for item in images:
        key = str(item.get("image_id") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def compose_compare_answer(
    question: str,
    sources: list[dict],
    comparison: dict | None = None,
    all_images: list[dict] | None = None,
) -> str:
    docs: dict[str, list[dict]] = {}
    for src in sources:
        docs.setdefault(src.get("doc_id", ""), []).append(src)

    if is_compare_question(question) and len(docs) >= 2:
        lines = ["根据检索到的规范，对比结果如下："]
        for doc_id, items in list(docs.items())[:2]:
            lines.append(f"- {doc_id}：")
            for item in items[:3]:
                lines.append(
                    f"  - §{item.get('number', '')} {item.get('title', '')}。"
                    f"{(item.get('content') or '')[:120]}"
                )
        if comparison and comparison.get("comparison_hint"):
            lines.append(f"对比提示：{comparison['comparison_hint']}")
        image_lines: list[str] = []
        for img in (all_images or [])[:3]:
            page = img.get("page_num") or img.get("page") or "?"
            caption = img.get("caption") or img.get("description") or ""
            image_lines.append(
                f"- {img.get('doc_id', '')} 图{img.get('image_id', '')} 第{page}页：{caption}"
            )
        if image_lines:
            lines.append("相关图示：")
            lines.extend(image_lines)
        return "\n".join(lines)
    return summarize_sources(sources)


def summarize_sources(sources: list[dict]) -> str:
    if not sources:
        return "已达最大推理步数，但未找到足够的相关章节。"
    snippets = []
    for src in sources[:3]:
        snippets.append(
            f"[{src.get('doc_id', '')} §{src.get('number', '')}] {src.get('title', '')}\n"
            f"{(src.get('content') or '')[:200]}"
        )
    return "已达最大推理步数，基于已检索内容：\n\n" + "\n\n".join(snippets)
