"""LLM-based SPO (Subject-Predicate-Object) triple extractor for named knowledge graphs."""
from __future__ import annotations

import json
import logging
from typing import Callable

from ..ai.llm_service import get_llm_service

logger = logging.getLogger(__name__)

PRED_TYPES = {
    "HAS_PROPERTY", "REQUIRES", "USES", "COMPOSED_OF",
    "CONSTRAINED_BY", "APPLIES_TO", "PART_OF", "RELATED_TO",
}

_SPO_MODEL: str | None = None


def set_spo_model(model: str) -> None:
    global _SPO_MODEL
    _SPO_MODEL = model


def _call_llm(prompt: str, max_tokens: int = 512) -> str | None:
    try:
        # timeout=90 fails fast instead of waiting the full 120s LLM_TIMEOUT
        kwargs: dict = {"temperature": 0, "max_tokens": max_tokens, "timeout": 90}
        if _SPO_MODEL:
            kwargs["model"] = _SPO_MODEL
        return get_llm_service().chat(
            [{"role": "user", "content": prompt}],
            **kwargs,
        )
    except Exception as exc:
        logger.warning("LLM 调用失败: %s", exc)
        return None


def _parse_section_block(raw_block: str) -> list[dict]:
    """Parse a flat JSON array of triples from one section's block."""
    start = raw_block.find("[")
    end = raw_block.rfind("]")
    if start == -1 or end <= start:
        return []
    try:
        data = json.loads(raw_block[start: end + 1])
    except json.JSONDecodeError as exc:
        logger.warning("JSON 解析失败: %s | block=%s", exc, raw_block[start: start + 200])
        return []
    if not isinstance(data, list):
        return []
    triples = []
    for t in data:
        if not isinstance(t, dict):
            continue
        s = str(t.get("s", "")).strip()
        p = str(t.get("p", "")).strip()
        o = str(t.get("o", "")).strip()
        if not (s and p and o):
            continue
        p_type = t.get("p_type", "RELATED_TO")
        if p_type not in PRED_TYPES:
            p_type = "RELATED_TO"
        triples.append({
            "s": s, "s_type": t.get("s_type", "Concept"),
            "p": p, "p_type": p_type,
            "o": o, "o_type": t.get("o_type", "Concept"),
        })
    return triples


def _extract_spo_batch(sections: list[dict]) -> list[dict]:
    """Extract SPO triples from a small batch of sections in one LLM call."""
    if not sections:
        return []

    # Build prompt with clearly delimited sections
    section_texts = []
    for sec in sections:
        content = (sec.get("content") or "").strip()
        if not content or len(content) < 20:
            section_texts.append(f"[{sec['chunk_id']}]\n(无内容)")
            continue
        section_texts.append(
            f"[{sec['chunk_id']}] {sec.get('number','')} {sec.get('title','')}\n"
            f"{content[:400]}"   # 400 chars = sufficient context, less tokens → faster
        )

    joined = "\n\n".join(section_texts)

    # /no_think: Qwen3 directive to skip chain-of-thought and output JSON directly.
    # Harmless on non-Qwen3 models (treated as plain text).
    prompt = (
        "/no_think\n"
        "从以下各章节分别提取 SPO 三元组，每节输出独立 JSON 数组，格式如下：\n\n"
        "===SECTION {chunk_id}===\n"
        '[{"s":"主体","s_type":"Tool","p":"谓词","p_type":"USES","o":"客体","o_type":"Process"}]\n\n'
        "实体类型: System Component Process Material Tool Parameter Standard Requirement Organization Concept\n"
        "关系类型: HAS_PROPERTY REQUIRES USES COMPOSED_OF CONSTRAINED_BY APPLIES_TO PART_OF RELATED_TO\n"
        "规则: 每节最多 6 条三元组; 无实体则输出 []; 只输出 JSON，不加注释\n\n"
        f"章节内容:\n{joined}\n\n"
        "输出(每节 ===SECTION <chunk_id>=== 后跟 JSON 数组):"
    )

    # 512 tokens per section is enough for 6 triples (~250 tokens) with headroom
    max_tokens = 512 * len(sections)
    raw = _call_llm(prompt, max_tokens=max_tokens)
    if raw is None:
        return [{"chunk_id": s["chunk_id"], "triples": []} for s in sections]

    # Parse each section block from the response
    results = []
    for sec in sections:
        cid = sec["chunk_id"]
        # Find this section's block in the response
        marker = f"===SECTION {cid}==="
        idx = raw.find(marker)
        if idx == -1:
            results.append({"chunk_id": cid, "triples": []})
            continue
        # Find next marker or end of string
        next_idx = raw.find("===SECTION ", idx + len(marker))
        block = raw[idx + len(marker): next_idx] if next_idx != -1 else raw[idx + len(marker):]
        triples = _parse_section_block(block)
        results.append({"chunk_id": cid, "triples": triples})

    return results


def _extract_spo_single(section: dict) -> list[dict]:
    """Extract SPO triples from one section; returns a list of triple dicts."""
    results = _extract_spo_batch([section])
    return results[0]["triples"] if results else []


def extract_spo_from_sections(
    sections: list[dict],
    on_progress: Callable[[int, int], None] | None = None,
    batch_size: int = 3,
) -> list[dict]:
    """Extract SPO triples from all sections, batched for efficiency."""
    results: list[dict] = []
    total = len(sections)
    for i in range(0, total, batch_size):
        if on_progress:
            on_progress(i, total)
        batch = sections[i: i + batch_size]
        results.extend(_extract_spo_batch(batch))
    if on_progress:
        on_progress(total, total)
    total_triples = sum(len(r["triples"]) for r in results)
    logger.info("SPO 提取完成: %d 章节, %d 三元组", len(results), total_triples)
    return results
