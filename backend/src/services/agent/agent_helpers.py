from __future__ import annotations

import re

_COMPARE_TOPIC_HINTS = ("安装要求", "材料要求", "检验标准", "存储要求", "安装前检查")


def extract_compare_doc_ids(question: str) -> list[str]:
    doc_ids = []
    seen: set[str] = set()
    for doc_id in re.findall(r"CPS\d{3,4}", (question or "").upper()):
        if doc_id in seen:
            continue
        seen.add(doc_id)
        doc_ids.append(doc_id)
    return doc_ids


def build_compare_topic(question: str) -> str:
    doc_ids = extract_compare_doc_ids(question)
    topic = re.sub(r"CPS\d{3,4}", "", question)
    topic = re.sub(r"[和与及,，。？?比较不同差异区别有什么对比]\s*", " ", topic)
    topic = re.sub(r"\s+", " ", topic).strip() or "相关要求"
    if len(doc_ids) >= 2:
        return " ".join([topic, *_COMPARE_TOPIC_HINTS]).strip()
    return topic


def is_compare_question(question: str) -> bool:
    text = question or ""
    compare_words = ("不同", "差异", "区别", "比较", "有什么不同", "对比")
    return len(re.findall(r"CPS\d{3,4}", text.upper())) >= 2 and any(
        word in text for word in compare_words
    )


def build_compare_plan(question: str) -> list[dict]:
    doc_ids = extract_compare_doc_ids(question)
    if len(doc_ids) < 2:
        return []
    compare_topic = build_compare_topic(question)
    return [
        {"name": "search_sections", "input": {"query": compare_topic, "doc_id": doc_ids[0], "top_k": 5}},
        {"name": "search_sections", "input": {"query": compare_topic, "doc_id": doc_ids[1], "top_k": 5}},
        {
            "name": "compare_documents",
            "input": {
                "doc_id_a": doc_ids[0],
                "doc_id_b": doc_ids[1],
                "topic": compare_topic,
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


def _section_excerpt(item: dict, limit: int = 120) -> str:
    raw = " ".join(
        str(item.get(key) or "").strip()
        for key in ("content", "description")
        if item.get(key)
    ).strip()
    raw = re.sub(r"\s+", " ", raw)
    if not raw:
        return ""

    number = str(item.get("number") or "").strip()
    title = str(item.get("title") or "").strip()
    for prefix in (
        f"{number} {title}".strip(),
        title,
        number,
    ):
        if prefix and raw.startswith(prefix):
            raw = raw[len(prefix):].lstrip("：:，,。．. -—")
            break

    if not raw:
        return ""

    raw = re.sub(r"[A-Za-z][A-Za-z0-9\-\(\)\/\.\s]{2,}", " ", raw)
    raw = re.sub(r"\s+", " ", raw).strip()
    if not raw:
        return ""

    parts = re.split(r"(?<=[。！？!?；;])\s*", raw)
    excerpt = parts[0].strip() if parts and parts[0].strip() else raw.strip()
    if len(excerpt) > limit:
        excerpt = excerpt[:limit].rstrip("，,；;：: ") + "…"
    return excerpt


def compose_compare_answer(
    question: str,
    sources: list[dict],
    comparison: dict | None = None,
    all_images: list[dict] | None = None,
) -> str:
    docs: dict[str, list[dict]] = {}
    for src in sources:
        docs.setdefault(src.get("doc_id", ""), []).append(src)

    if is_compare_question(question):
        requested_ids = extract_compare_doc_ids(question)
        ordered_doc_ids = requested_ids or list(docs.keys())
        lines = ["## 对比结果", ""]
        if len(ordered_doc_ids) < 2 and len(docs) >= 2:
            ordered_doc_ids = list(docs.keys())[:2]
        missing_docs: list[str] = []
        for doc_id in ordered_doc_ids[:2]:
            items = docs.get(doc_id, [])
            lines.append(f"### {doc_id or '未识别规范'}")
            lines.append("")
            if not items:
                lines.append("- 当前检索结果未找到该规范的直接相关内容")
                missing_docs.append(doc_id)
            else:
                for item in items:
                    number = item.get("number", "")
                    title = item.get("title", "")
                    content = _section_excerpt(item)
                    bullet = f"- §{number} {title}".strip()
                    if content:
                        bullet += f"\n  {content}"
                    lines.append(bullet)
            lines.append("")
        if comparison and comparison.get("comparison_hint"):
            lines.extend(["### 对比提示", "", f"- {comparison['comparison_hint']}", ""])
        if missing_docs:
            lines.extend(
                [
                    "### 结论",
                    "",
                    "- 当前检索结果中，部分规范未检到足够直接内容，",
                    "  不能据此判断两者“没有差异”。",
                    "- 建议继续查看更具体的安装要求、材料要求或检验标准章节。",
                    "",
                ]
            )
        if all_images:
            lines.extend(["### 相关图示", ""])
            for img in all_images:
                figure_label = str(img.get("figure_label") or "").strip()
                if not figure_label:
                    figure_labels = img.get("figure_labels")
                    if isinstance(figure_labels, list) and figure_labels:
                        figure_label = str(figure_labels[0]).strip()
                caption = str(img.get("caption") or img.get("description") or "").strip()
                page_num = img.get("page_num")
                doc_id = str(img.get("doc_id") or "").strip()
                header = " · ".join(
                    part
                    for part in (
                        figure_label,
                        doc_id,
                        f"第{page_num}页" if page_num else "",
                    )
                    if part
                )
                lines.append(f"- {header or '图示'}")
                if caption:
                    lines.append(f"  {caption}")
            lines.append("")
        return "\n".join(lines).strip()
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
