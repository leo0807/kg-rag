"""
src/routers/query/stream_multimodal.py
多模态检索策略流式生成器：文字检索 + 图片 caption 检索 + 图文融合回答。
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import AsyncGenerator

from ...core.config import settings as app_settings
from ...services.ai.llm import clean_llm_response
from ...services.ai.llm_service import get_llm_service
from .context_utils import build_llm_context, reorder_sources_for_llm
from .stream_utils import (
    _emit_follow_ups, build_metrics_event, clean_stream_chunk,
    emit_status_event, estimate_answer_max_tokens,
    get_question_handler_for, serialize_sources,
    stream_with_first_token_logging,
)

logger = logging.getLogger(__name__)

_MULTIMODAL_SYSTEM_PROMPT = (
    "你是一个航空制造工艺规范专家助手。请根据提供的规范内容，用中文准确回答问题。\n"
    "图片引用规则：\n"
    "- 如果答案需要图示说明，可以引用 sources 中提供的图片\n"
    "- 引用格式：[IMG: image_id 说明文字]，如 [IMG: CPS1000_p12_img2 孔位示意图]\n"
    "- 只引用来源中实际提供的图片，禁止编造不存在的 image_id\n"
    "- 重要：规范编号必须与来源章节完全一致，不得自行修改或补全"
)


def _build_image_context(
    caption_images: list[dict],
    section_images: list[dict],
) -> str:
    """将图片列表构建为 LLM 可读的上下文字符串。"""
    all_imgs: dict[str, dict] = {}
    for img in caption_images + section_images:
        iid = img.get("image_id") or ""
        if iid and iid not in all_imgs:
            all_imgs[iid] = img
    if not all_imgs:
        return ""
    lines = ["## 相关图片（可引用）"]
    for iid, img in list(all_imgs.items())[:6]:
        caption = img.get("caption") or img.get("description") or ""
        lines.append(f"- image_id: {iid}  描述: {caption}")
    return "\n".join(lines)


async def stream_multimodal_query(
    driver,
    question:      str,
    top_k:         int,
    use_hyde:      bool,
    hyde_alpha:    float,
    doc_id:        str,
    history:       list[dict],
    image_context: str,
    t_start:       float,
    user_id:       str,
    department:    str,
) -> AsyncGenerator[str, None]:
    from ...services.retrieval.multimodal_search import multimodal_search

    yield emit_status_event("多模态检索：文字 + 图片...")

    try:
        sections, ft_score_map, caption_images, expansion_info = await multimodal_search(
            driver=driver,
            question=question,
            strategy="parallel",
            top_k=top_k,
            use_hyde=use_hyde,
            hyde_alpha=hyde_alpha,
            doc_id=doc_id,
        )
    except Exception as e:
        logger.error("multimodal_search 失败: %s", e)
        yield f"data: {json.dumps({'type': 'delta', 'content': '多模态检索失败，请重试。'}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"
        return

    _retrieval_ms = int((time.time() - t_start) * 1000)

    if expansion_info:
        yield f"data: {json.dumps({'type': 'expansion', 'content': expansion_info}, ensure_ascii=False)}\n\n"

    sources = serialize_sources(sections, ft_score_map)
    yield f"data: {json.dumps({'type': 'sources', 'content': sources}, ensure_ascii=False)}\n\n"

    # 发送图片事件（前端用于 AnswerImageGallery）
    all_section_imgs = []
    for sec in sections:
        all_section_imgs.extend(sec.get("section_images") or [])
    combined_images = {img["image_id"]: img for img in caption_images + all_section_imgs if img.get("image_id")}
    if combined_images:
        yield f"data: {json.dumps({'type': 'images', 'content': list(combined_images.values())[:8]}, ensure_ascii=False)}\n\n"

    if not sections:
        yield f"data: {json.dumps({'type': 'delta', 'content': '在知识库中未找到相关内容。'}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"
        return

    yield emit_status_event("正在生成答案...")

    llm_sections = reorder_sources_for_llm(sections, question)
    context = build_llm_context(llm_sections)
    img_context = _build_image_context(caption_images, all_section_imgs)
    if img_context:
        context = context + "\n\n" + img_context
    if image_context:
        context = context + "\n\n" + image_context

    answer_max_tokens = estimate_answer_max_tokens(question, context)
    _qtype, _handler, _type_label = get_question_handler_for(question)
    if _type_label:
        yield emit_status_event(_type_label)

    messages = [{"role": "system", "content": _MULTIMODAL_SYSTEM_PROMPT + (
        " " + _handler.system_addon() if _handler.system_addon() else ""
    )}]
    for h in history[-6:]:
        messages.append({"role": h.get("role", "user"), "content": h.get("content", "")})
    user_text = f"## 相关规范内容\n\n{context}\n\n## 问题\n\n{question}" + _handler.user_suffix()
    messages.append({"role": "user", "content": user_text})

    full_answer = ""
    try:
        async for delta in stream_with_first_token_logging(
            get_llm_service(),
            messages,
            timeout=int(getattr(app_settings, "LLM_STREAM_TIMEOUT", 120)),
            max_tokens=answer_max_tokens,
            t_start=t_start,
            logger=logger,
        ):
            delta = clean_stream_chunk(delta)
            if delta:
                full_answer += delta
                yield f"data: {json.dumps({'type': 'delta', 'content': delta}, ensure_ascii=False)}\n\n"
    except Exception as e:
        logger.error("multimodal LLM 流失败: %s", e)

    latency_ms = int((time.time() - t_start) * 1000)
    yield build_metrics_event(latency_ms, _retrieval_ms, len(sections), len(sources))

    fu = await _emit_follow_ups(question, full_answer, [s.get("doc_id") for s in sections if s.get("doc_id")])
    if fu:
        yield f"data: {fu}\n\n"

    yield "data: [DONE]\n\n"
