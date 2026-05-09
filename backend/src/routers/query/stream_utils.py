from __future__ import annotations

import asyncio
import json
import logging
import re
import time

from ...services.ai.llm_service import get_llm_service, LLMError

logger = logging.getLogger(__name__)


def emit_status_event(content: str) -> str:
    return f"data: {json.dumps({'type': 'status', 'content': content}, ensure_ascii=False)}\n\n"


def clean_stream_chunk(chunk: str | None) -> str:
    if not chunk:
        return ""
    if any(marker in chunk for marker in ("user##", "##assistant", "<|user|>", "<|im_start|>")):
        return ""
    return chunk.replace("\ufffd", "")


def estimate_answer_max_tokens(question: str, context: str, cap: int = 800) -> int:
    estimated = 160 + len(question) // 2 + len(context) // 9
    return max(256, min(cap, estimated))


def serialize_sources(sections: list[dict], ft_score_map: dict[str, float]) -> list[dict]:
    sources = []
    for s in sections:
        sources.append(
            {
                "chunk_id": s["chunk_id"],
                "doc_id": s["doc_id"],
                "number": s.get("number") or "",
                "title": s.get("title") or "",
                "score": round(
                    s.get("score")
                    or s.get("rrf_score")
                    or s.get("rerank_score")
                    or ft_score_map.get(s["chunk_id"], 0.0),
                    4,
                ),
                "page_idx": s.get("page_idx"),
                "bbox": s.get("bbox"),
                "source_type": s.get("source_type", []),
                "retrieval_trace": s.get("retrieval_trace", []),
                "is_graph_expanded": bool(s.get("is_graph_expanded")),
                "is_vector_hit": bool(s.get("is_vector_hit")),
                "is_fulltext_hit": bool(s.get("is_fulltext_hit")),
                "is_gnn_hit": bool(s.get("is_gnn_hit")),
            }
        )
    return sources


async def try_semantic_cache_lookup(
    question: str,
    strategy: str,
    timeout_s: float,
):
    from ...services.retrieval.embedder import get_cached_embedding
    from ...services.retrieval import semantic_cache

    t0 = time.time()
    try:
        q_emb = await asyncio.wait_for(
            asyncio.to_thread(get_cached_embedding, question),
            timeout=timeout_s,
        )
        logger.info("[timing] 语义缓存向量化 %.2fs", time.time() - t0)
        hit = q_emb and semantic_cache.lookup(list(q_emb), strategy)
        logger.info("[timing] 语义缓存检索 %.2fs", time.time() - t0)
        return q_emb, hit
    except asyncio.TimeoutError:
        logger.info("[timing] 语义缓存超时 %.2fs，跳过", time.time() - t0)
        return None, None


async def stream_semantic_cache_hit(
    hit: dict,
    question: str,
    user_id: str,
    department: str,
    strategy: str,
):
    sim = hit.get("similarity", 0)
    yield f"data: {json.dumps({'type': 'status', 'content': f'⚡ 语义缓存命中（相似度 {sim:.3f}）'}, ensure_ascii=False)}\n\n"
    yield f"data: {json.dumps({'type': 'sources', 'content': hit.get('sources', [])}, ensure_ascii=False)}\n\n"
    cached_answer = clean_llm_response(hit.get("answer", ""))
    for char in cached_answer:
        yield f"data: {json.dumps({'type': 'delta', 'content': char}, ensure_ascii=False)}\n\n"
    yield "data: [DONE]\n\n"
    try:
        from ...db.session import AsyncSessionLocal
        from ...db.models import CacheHit
        tok = max(100, len(cached_answer) // 3)
        async with AsyncSessionLocal() as db_session:
            db_session.add(CacheHit(
                user_id=user_id, department=department,
                question_preview=question[:200],
                matched_question_preview=hit.get("question_preview", "")[:200],
                similarity=sim, strategy=strategy,
                cache_id=hit.get("cache_id", ""),
                prompt_tokens_saved=tok, cost_saved_usd=round(tok * 0.000002, 6),
            ))
            await db_session.commit()
    except Exception as _ce:
        logger.warning("CacheHit 写入失败: %s", _ce)


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


async def stream_with_first_token_logging(
    llm,
    messages: list[dict],
    timeout: int,
    t_start: float,
    logger: logging.Logger,
):
    first_token_logged = False
    async for chunk in llm.stream_chat(messages, timeout=timeout):
        if not first_token_logged:
            logger.info("[timing] 首token t=%.2fs", time.time() - t_start)
            first_token_logged = True
        yield chunk
