from __future__ import annotations

import asyncio
import re
from collections import defaultdict

from ..agent.agent_helpers import extract_compare_doc_ids
from ..ai.llm import clean_llm_response
from ..ai.service import get_llm_service
from ...prompts import registry

def _clean_text(text: str | None, limit: int = 180) -> str:
    if not text:
        return ""
    raw = re.sub(r"\s+", " ", str(text)).strip()
    raw = re.sub(r"(?:,|\uFF0C|\u3001|\u3002|\.)\s*(?:,|\uFF0C|\u3001|\u3002|\.)+", "，", raw)
    raw = re.sub(r"[A-Za-z][A-Za-z0-9\-\(\)\/\.\s]{2,}", " ", raw)
    raw = re.sub(r"\s+", " ", raw).strip()
    if len(raw) > limit:
        raw = raw[:limit].rstrip("，,；;：: ") + "…"
    return raw


def _section_relevance(question: str, item: dict, doc_id: str) -> int:
    text = " ".join(
        str(item.get(key) or "").lower()
        for key in ("number", "title", "content", "description")
    )
    score = 0
    doc = str(doc_id or "").upper()
    if doc and doc in (question or "").upper():
        score += 3
    for kw in ("密封圈", "o 型密封圈", "密封挡圈", "密封", "安装", "安装前", "检查", "检验", "要求"):
        if kw in text:
            score += 2
    for kw in ("图", "figure", "fig"):
        if kw in text:
            score += 1
    if re.search(r"7\.5|6\.1|6\.2|6\.3|6\.4|9\.3", text):
        score += 1
    return score


def _figure_label(raw: str | None) -> str:
    if not raw:
        return ""
    text = str(raw).strip().replace(".", "-")
    if not text:
        return ""
    if text.lower().startswith("图"):
        return text
    return f"图{text}"


def _build_context(question: str, sections: list[dict], images: list[dict] | None) -> str:
    requested_ids = extract_compare_doc_ids(question)
    grouped: dict[str, list[dict]] = defaultdict(list)
    for item in sections:
        grouped[str(item.get("doc_id") or "")].append(item)

    doc_ids = requested_ids or list(grouped.keys())
    lines = []
    for doc_id in doc_ids[:2]:
        lines.append(f"【来源规范：{doc_id}】")
        items = sorted(
            grouped.get(doc_id, []),
            key=lambda item: (-_section_relevance(question, item, doc_id), str(item.get("number") or "")),
        )
        for item in items[:5]:
            number = str(item.get("number") or "").strip()
            title = str(item.get("title") or "").strip()
            content = _clean_text(item.get("content") or item.get("description") or "")
            header = " ".join(part for part in (f"§{number}" if number else "", title) if part)
            if content:
                lines.append(f"- {header}\n  {content}")
            else:
                lines.append(f"- {header}")
        lines.append("")
    if images:
        lines.append("【参考图示】")
        for img in images:
            fig = _figure_label(img.get("figure_label") or (img.get("figure_labels") or [None])[0])
            if not fig:
                fig = _figure_label(
                    re.search(
                        r"(图\s*[0-9]+(?:[-.][0-9]+)+|图\s*[0-9]+-\d+)",
                        " ".join(
                            str(img.get(key) or "") for key in ("caption", "description")
                        ),
                    ).group(1)
                    if re.search(
                        r"(图\s*[0-9]+(?:[-.][0-9]+)+|图\s*[0-9]+-\d+)",
                        " ".join(
                            str(img.get(key) or "") for key in ("caption", "description")
                        ),
                    )
                    else ""
                )
            caption = _clean_text(img.get("caption") or img.get("description") or "", limit=120)
            doc_id = str(img.get("doc_id") or "").strip()
            page_num = img.get("page_num")
            meta = " · ".join(
                part for part in (fig, doc_id, f"第{page_num}页" if page_num else "") if part
            )
            if meta:
                lines.append(f"- {meta}")
            if caption:
                lines.append(f"  {caption}")
        lines.append("")
    lines.append(f"【问题】\n{question}")
    return "\n".join(lines).strip()


def _fallback_compare_answer(question: str, sections: list[dict], images: list[dict] | None) -> str:
    docs: dict[str, list[dict]] = defaultdict(list)
    for src in sections:
        docs[str(src.get("doc_id") or "")].append(src)
    doc_ids = extract_compare_doc_ids(question) or list(docs.keys())
    lines = ["## 对比结果", ""]
    for doc_id in doc_ids[:2]:
        lines.append(f"### {doc_id or '未识别规范'}")
        lines.append("")
        items = docs.get(doc_id, [])
        if not items:
            lines.append("- 当前检索结果未找到该规范的直接相关内容")
        else:
            for item in items[:4]:
                number = item.get("number", "")
                title = item.get("title", "")
                content = _clean_text(item.get("content") or item.get("description") or "", limit=120)
                bullet = f"- §{number} {title}".strip()
                if content:
                    bullet += f"\n  {content}"
                lines.append(bullet)
        lines.append("")
    if images:
        lines.append(_render_images_section(images))
    return "\n".join(lines).strip()


def _render_images_section(images: list[dict]) -> str:
    lines = ["### 相关图示", ""]
    for img in images[:6]:
        fig = _figure_label(img.get("figure_label") or (img.get("figure_labels") or [None])[0])
        caption = _clean_text(img.get("caption") or img.get("description") or "", limit=100)
        meta = " · ".join(
            part
            for part in (
                fig,
                str(img.get("doc_id") or "").strip(),
                f"第{img.get('page_num')}页" if img.get("page_num") else "",
            )
            if part
        )
        lines.append(f"- {meta or '图示'}")
        if caption:
            lines.append(f"  {caption}")
    lines.append("")
    return "\n".join(lines).strip()


async def summarize_compare_answer(
    question: str,
    sections: list[dict],
    images: list[dict] | None = None,
) -> str:
    context = _build_context(question, sections, images or [])
    requested_ids = extract_compare_doc_ids(question)
    doc_a = requested_ids[0] if len(requested_ids) > 0 else "CPSXXXX"
    doc_b = requested_ids[1] if len(requested_ids) > 1 else "CPSYYYY"
    prompt_data = registry.render(
        "agent_compare",
        context=context,
        question=question,
        doc_a=doc_a,
        doc_b=doc_b,
    )
    try:
        answer = await asyncio.to_thread(
            get_llm_service().chat,
            prompt_data["messages"],
            "",
        )
        answer = clean_llm_response(answer)
        if not answer:
            raise ValueError("empty compare summary")
        # Fix '# # X' / '## # X' headings that LLM generates when it mixes context
        # structure with the output template — convert to canonical ## / ### levels.
        answer = re.sub(r"(?m)^(#{1,4}) # ", r"\1# ", answer)
        allowed_ids = set(extract_compare_doc_ids(question))
        answer_ids = set(re.findall(r"CPS\d{3,4}", answer.upper()))
        if allowed_ids:
            if answer_ids and not answer_ids.issubset(allowed_ids):
                return _fallback_compare_answer(question, sections, images)
            if not allowed_ids.issubset(answer_ids):
                return _fallback_compare_answer(question, sections, images)
        # Strip any echoed context section (LLM sometimes copies the ## 相关图示 header
        # from the context block verbatim); we'll re-append a canonical ### version below.
        answer = re.sub(r"(?m)^#{1,4}\s*相关图示\s*\n((?:(?!^#).*\n)*)", "", answer).strip()
        if images:
            answer = f"{answer}\n\n{_render_images_section(images)}"
        return answer
    except Exception:
        return _fallback_compare_answer(question, sections, images)
