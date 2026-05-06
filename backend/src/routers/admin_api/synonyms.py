"""
GET  /api/admin/synonyms        — 列出所有词典条目
POST /api/admin/synonyms        — 新增/覆盖一个词条 {term, synonyms}
DELETE /api/admin/synonyms/{term} — 删除一个词条
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ...auth.deps import get_admin_user
from ...db.models import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"])

_SYNONYMS_FILE = Path(__file__).resolve().parents[2] / "data" / "synonyms.json"


def _read() -> dict[str, list[str]]:
    try:
        return json.loads(_SYNONYMS_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


def _write(data: dict[str, list[str]]) -> None:
    _SYNONYMS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SYNONYMS_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # 使 query_expander 的 lru_cache 失效
    try:
        from ...services.retrieval.query_expander import reload_synonyms
        reload_synonyms()
    except Exception:
        pass


class SynonymEntry(BaseModel):
    term: str
    synonyms: list[str]


@router.get("/synonyms")
async def list_synonyms(_: User = Depends(get_admin_user)):
    data = _read()
    return {
        "total": len(data),
        "entries": [{"term": k, "synonyms": v} for k, v in sorted(data.items())],
    }


@router.post("/synonyms", status_code=201)
async def upsert_synonym(entry: SynonymEntry, _: User = Depends(get_admin_user)):
    term = entry.term.strip()
    syns = [s.strip() for s in entry.synonyms if s.strip()]
    if not term:
        raise HTTPException(400, "term 不能为空")
    if not syns:
        raise HTTPException(400, "synonyms 不能为空列表")
    data = _read()
    data[term] = syns
    _write(data)
    logger.info("近义词写入: %s → %s", term, syns)
    return {"term": term, "synonyms": syns}


@router.delete("/synonyms/{term}", status_code=200)
async def delete_synonym(term: str, _: User = Depends(get_admin_user)):
    data = _read()
    if term not in data:
        raise HTTPException(404, f"词条 '{term}' 不存在")
    del data[term]
    _write(data)
    logger.info("近义词删除: %s", term)
    return {"deleted": term}
