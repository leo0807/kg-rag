from __future__ import annotations

import asyncio
import json
import logging
import re
import time

from ...services.ai.llm_service import get_llm_service, LLMError
from ...services.answer_humanizer import humanize_answer_text
from ...services.agent.agent_helpers import extract_compare_doc_ids

logger = logging.getLogger(__name__)


def emit_status_event(content: str) -> str:
    return f"data: {json.dumps({'type': 'status', 'content': content}, ensure_ascii=False)}\n\n"


def clean_stream_chunk(chunk: str | None) -> str:
    if not chunk:
        return ""
    if any(marker in chunk for marker in ("user##", "##assistant", "<|user|>", "<|im_start|>")):
        return ""
    chunk = chunk.replace("\ufffd", "")
    chunk = re.sub(r'(?:is){3,}', '', chunk)
    chunk = re.sub(r'N{3,}', '', chunk)
    chunk = re.sub(r'isis[Nn]*', '', chunk)
    return chunk


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


def build_metrics_event(latency_ms: int, retrieval_ms: int, section_count: int, source_count: int) -> str:
    payload = {
        "type": "metrics",
        "content": {
            "latency_ms": latency_ms,
            "retrieval_ms": retrieval_ms,
            "section_count": section_count,
            "source_count": source_count,
        },
    }
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def get_question_handler_for(question: str):
    from ...services.qa.mcq_handler import detect_question_type, QuestionType
    from ...services.qa.question_handlers import get_question_handler

    qtype = detect_question_type(question)
    handler = get_question_handler(qtype)
    type_label = {
        QuestionType.MULTIPLE_CHOICE: '🧮 识别为选择题',
        QuestionType.MULTIPLE_SELECT: '🧮 识别为多选题',
        QuestionType.TRUE_FALSE: '🧮 识别为判断题',
        QuestionType.FILL_BLANK: '🧮 识别为填空题',
        QuestionType.SHORT_ANSWER: '🧮 识别为简答题',
        QuestionType.OPEN: '',
    }.get(qtype, '')
    return qtype, handler, type_label


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
    cached_answer = humanize_answer_text(clean_llm_response(hit.get("answer", "")))
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


def _build_follow_up_fallback(question: str, allowed_doc_ids: list[str]) -> list[str]:
    compare_words = ("不同", "差异", "区别", "比较", "对比")
    doc_ids: list[str] = []
    for doc_id in extract_compare_doc_ids(question) + [doc_id for doc_id in allowed_doc_ids if doc_id]:
        if doc_id not in doc_ids:
            doc_ids.append(doc_id)
    if len(doc_ids) >= 2 and any(word in question for word in compare_words):
        return [
            f"继续查看 {doc_ids[0]} 的安装要求",
            f"继续查看 {doc_ids[1]} 的安装要求",
            "进一步对比两份规范的检验标准",
        ]
    if len(doc_ids) == 1:
        return [
            f"查看 {doc_ids[0]} 的相关章节",
            f"继续追问 {doc_ids[0]} 的安装要求",
            f"查看 {doc_ids[0]} 的检验标准",
        ]
    return []


async def _emit_follow_ups(question: str, answer: str, allowed_doc_ids: list[str] | None = None):
    """生成并 yield 追问建议 SSE 事件；失败静默跳过。"""
    question_doc_ids = extract_compare_doc_ids(question)
    allowed_doc_ids = [doc_id for doc_id in (allowed_doc_ids or []) if doc_id]
    primary_doc_ids = question_doc_ids or allowed_doc_ids
    allowed_set = set(primary_doc_ids)
    try:
        allowed_text = "、".join(primary_doc_ids) if primary_doc_ids else "当前回答涉及的来源"
        msgs = [
            {
                "role": "system",
                "content": (
                    "只输出一个 JSON 数组，格式：[\"问题1\",\"问题2\",\"问题3\"]，每条不超过30字，不要其他内容。"
                    "只允许围绕已知来源规范生成追问，不得引入不存在的规范编号。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"用户问题：{question}\n"
                    f"系统答案（节选）：{answer[:400]}\n"
                    f"可引用的规范编号：{allowed_text}\n\n"
                    "请生成3条追问建议："
                ),
            },
        ]
        raw = await asyncio.wait_for(
            asyncio.to_thread(get_llm_service().chat, msgs), timeout=8.0
        )
        m = re.search(r'\[.*?\]', raw, re.DOTALL)
        if m:
            items = json.loads(m.group())
            questions = []
            for q in items:
                text = str(q).strip()
                if not text:
                    continue
                cps_refs = set(re.findall(r"CPS\d{3,4}", text.upper()))
                if cps_refs and allowed_set and not cps_refs.issubset(allowed_set):
                    continue
                if "CPS111" in text.upper():
                    continue
                questions.append(text)
                if len(questions) >= 3:
                    break
            if questions:
                return json.dumps({"type": "follow_up", "content": questions}, ensure_ascii=False)
    except Exception as _e:
        logger.debug("追问建议生成失败（跳过）: %s", _e)
    fallback = _build_follow_up_fallback(question, primary_doc_ids)
    if fallback:
        return json.dumps({"type": "follow_up", "content": fallback[:3]}, ensure_ascii=False)
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
