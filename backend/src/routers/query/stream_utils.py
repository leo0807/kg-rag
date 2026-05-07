from __future__ import annotations

import asyncio
import json
import logging
import re

from ...services.ai.llm_service import get_llm_service, LLMError

logger = logging.getLogger(__name__)


def _error_event(e: Exception) -> str:
    """将异常序列化为 SSE error 事件字符串。"""
    if isinstance(e, LLMError):
        payload = {"type": "error", "code": e.code, "message": e.message,
                   "status_code": e.status_code, "endpoint": e.endpoint}
    else:
        payload = {"type": "error", "code": "unknown_error",
                   "message": "AI 服务异常，请联系管理员",
                   "status_code": None, "endpoint": ""}
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _format_section_ref(section: dict) -> str:
    """生成章节引用头，兼容 page_idx 为 None 的情况。"""
    doc_id = section.get("doc_id", "")
    number = section.get("number", "")
    title = section.get("title", "")
    page_idx = section.get("page_idx")
    page_text = f" (第{page_idx + 1}页)" if isinstance(page_idx, int) and page_idx >= 0 else ""
    return f"[{doc_id} §{number}{page_text}] {title}"


async def _emit_follow_ups(question: str, answer: str):
    """生成并 yield 追问建议 SSE 事件；失败静默跳过。"""
    try:
        msgs = [
            {"role": "system", "content": "只输出一个 JSON 数组，格式：[\"问题1\",\"问题2\",\"问题3\"]，每条不超过30字，不要其他内容。"},
            {"role": "user",   "content": f"用户问题：{question}\n系统答案（节选）：{answer[:400]}\n\n请生成3条追问建议："},
        ]
        raw = await asyncio.wait_for(
            asyncio.to_thread(get_llm_service().chat, msgs), timeout=8.0
        )
        m = re.search(r'\[.*?\]', raw, re.DOTALL)
        if m:
            items = json.loads(m.group())
            questions = [str(q).strip() for q in items if str(q).strip()][:3]
            if questions:
                return json.dumps({"type": "follow_up", "content": questions}, ensure_ascii=False)
    except Exception as _e:
        logger.debug("追问建议生成失败（跳过）: %s", _e)
    return None
