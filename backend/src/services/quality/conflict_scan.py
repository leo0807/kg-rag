from __future__ import annotations

"""扫描任务调度与结果持久化"""
import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from neo4j import Driver
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.models import ConflictRecord
from ...db.session import AsyncSessionLocal
from .conflict_detectors import detect_constraint_conflicts, fetch_entity_pairs, judge_pair

logger = logging.getLogger(__name__)

_scans: dict[str, dict[str, Any]] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _pair_key(row: dict) -> tuple:
    a, b = sorted([row["section_a_chunk_id"], row["section_b_chunk_id"]])
    return (row["entity_name"], a, b)


def _dedup(rows: list[dict]) -> list[dict]:
    seen: set = set()
    out: list[dict] = []
    for row in rows:
        key = _pair_key(row)
        if key not in seen:
            seen.add(key)
            out.append(row)
    return out


async def _save_conflicts(scan_id: str, rows: list[dict]) -> int:
    async with AsyncSessionLocal() as db:
        for row in rows:
            db.add(ConflictRecord(scan_id=scan_id, **row))
        await db.commit()
    return len(rows)


async def _run_scan(scan_id: str, driver: Driver, entity_limit: int, constraint_limit: int) -> None:
    scan = _scans[scan_id]
    scan["status"] = "running"
    scan["started_at"] = _now()
    try:
        scan["phase"] = "constraint"
        constraint_rows = await asyncio.to_thread(detect_constraint_conflicts, driver, constraint_limit)
        scan["constraint_count"] = len(constraint_rows)

        scan["phase"] = "entity_pairs"
        entity_pairs = await asyncio.to_thread(fetch_entity_pairs, driver, entity_limit)
        scan["entity_pairs_total"] = len(entity_pairs)

        semantic_rows: list[dict] = []
        for i, pair in enumerate(entity_pairs):
            scan["entity_pairs_done"] = i + 1
            result = await judge_pair(pair)
            if result:
                semantic_rows.append(result)
            await asyncio.sleep(0)

        scan["semantic_count"] = len(semantic_rows)
        all_rows = _dedup(constraint_rows + semantic_rows)
        await _save_conflicts(scan_id, all_rows)
        scan["status"] = "completed"
        scan["finished_at"] = _now()
        scan["total_conflicts"] = len(all_rows)
    except Exception as exc:
        logger.exception("冲突检测扫描失败 scan_id=%s", scan_id)
        scan["status"] = "failed"
        scan["finished_at"] = _now()
        scan["error"] = str(exc)


async def start_conflict_scan(
    driver: Driver,
    entity_limit: int = 60,
    constraint_limit: int = 200,
) -> dict[str, Any]:
    scan_id = uuid.uuid4().hex
    _scans[scan_id] = {
        "scan_id": scan_id, "status": "queued", "phase": "",
        "created_at": _now(), "started_at": None, "finished_at": None,
        "constraint_count": 0, "semantic_count": 0,
        "entity_pairs_total": 0, "entity_pairs_done": 0,
        "total_conflicts": 0, "error": "",
    }
    asyncio.create_task(_run_scan(scan_id, driver, entity_limit, constraint_limit))
    return _scans[scan_id]


def get_scan(scan_id: str) -> dict[str, Any]:
    scan = _scans.get(scan_id)
    if not scan:
        raise KeyError(scan_id)
    return scan


def list_scans(limit: int = 10) -> list[dict[str, Any]]:
    return sorted(_scans.values(), key=lambda s: str(s.get("created_at") or ""), reverse=True)[:limit]
