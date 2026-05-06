"""
冲突仲裁服务 — 存储和读取人工仲裁决定（Redis），以及为 RAG 注入冲突注释。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.models import ConflictRecord
from ..infra.cache import get_redis

DECISION_LABELS: dict[str, str] = {
    "use_a":           "以文档A为准",
    "use_b":           "以文档B为准",
    "both_applicable": "两者均适用（不同场景）",
    "expert_review":   "待专家介入",
}


def arb_key(conflict_id: int) -> str:
    return f"conflict:arb:{conflict_id}"


def store_arbitration(conflict_id: int, decision: str, note: str = "") -> None:
    r = get_redis()
    r.set(arb_key(conflict_id), json.dumps({
        "decision":  decision,
        "note":      note,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }))


def get_arbitration(conflict_id: int) -> dict | None:
    r = get_redis()
    raw = r.get(arb_key(conflict_id))
    return json.loads(raw) if raw else None


async def get_conflict_notes_for_chunks(
    chunk_ids: list[str], db: AsyncSession
) -> str:
    """
    根据检索到的 chunk_ids 查找相关冲突，返回供 LLM 上下文注入的注释字符串。
    已仲裁的冲突注明仲裁结论；未仲裁的提示存在冲突。
    """
    if not chunk_ids:
        return ""

    result = await db.execute(
        select(ConflictRecord)
        .where(
            or_(
                ConflictRecord.section_a_chunk_id.in_(chunk_ids),
                ConflictRecord.section_b_chunk_id.in_(chunk_ids),
            )
        )
        .limit(8)
    )
    conflicts = result.scalars().all()
    notes: list[str] = []

    for c in conflicts:
        arb = get_arbitration(c.id)
        if arb and arb["decision"] != "expert_review":
            label = DECISION_LABELS.get(arb["decision"], arb["decision"])
            extra = f"（{arb['note']}）" if arb.get("note") else ""
            notes.append(
                f"[已仲裁] {c.entity_name}：{label}{extra}"
            )
        elif c.status == "pending":
            notes.append(
                f"[⚠️ 规范冲突] {c.entity_name}："
                f"{c.section_a_doc_id} 与 {c.section_b_doc_id} 存在不一致，"
                f"请以最新版本为准。{c.description[:120]}"
            )

    if not notes:
        return ""
    return "=== 规范冲突注意事项 ===\n" + "\n".join(notes)
