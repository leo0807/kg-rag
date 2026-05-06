"""检索权重实验室 — 参数配置、预设管理、A/B 对比历史"""
from __future__ import annotations
import json, time, asyncio, logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Any
from ...auth.deps import get_admin_user
from ...db.models import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/lab", tags=["lab"])

GLOBAL_KEY  = "search:global_params"
HISTORY_KEY = "lab:ab_history"
PRESET_PFX  = "lab:preset:"

DEFAULT_PARAMS: dict[str, Any] = {
    "alpha": 0.5, "top_k": 5,
    "vector_weight": 1.0, "similarity_threshold": 0.0, "max_recall": 20,
    "bm25_weight": 1.0, "title_weight": 2.0, "fuzzy_match": "auto",
    "rrf_k": 60, "rerank_top_k": 5,
    "graph_hops": 1,
}


def _redis():
    import redis as _r
    from ...core.config import settings
    return _r.from_url(settings.REDIS_URL, decode_responses=True, socket_connect_timeout=2)


def _get_params() -> dict:
    try:
        raw = _redis().get(GLOBAL_KEY)
        if raw:
            return {**DEFAULT_PARAMS, **json.loads(raw)}
    except Exception:
        pass
    return dict(DEFAULT_PARAMS)


def _set_params(params: dict) -> None:
    r = _redis()
    r.set(GLOBAL_KEY, json.dumps(params))
    if "alpha" in params:
        r.set("search:hybrid_alpha", str(params["alpha"]))


@router.get("/params")
async def get_params(_: User = Depends(get_admin_user)):
    return await asyncio.to_thread(_get_params)


class ParamsUpdate(BaseModel):
    params: dict


@router.put("/params")
async def set_params(req: ParamsUpdate, _: User = Depends(get_admin_user)):
    merged = {**_get_params(), **req.params}
    await asyncio.to_thread(_set_params, merged)
    return {"status": "OK", "params": merged}


# ── Presets ───────────────────────────────────────────────────────────────────
@router.get("/presets")
async def list_presets(_: User = Depends(get_admin_user)):
    try:
        r = _redis()
        keys = r.keys(f"{PRESET_PFX}*")
        presets = []
        for k in sorted(keys):
            name = k[len(PRESET_PFX):]
            raw = r.get(k)
            if raw:
                presets.append({"name": name, "params": json.loads(raw)})
        return presets
    except Exception:
        return []


class PresetSave(BaseModel):
    name: str
    params: dict


@router.post("/presets")
async def save_preset(req: PresetSave, _: User = Depends(get_admin_user)):
    if not req.name.strip():
        raise HTTPException(400, "预设名称不能为空")
    _redis().set(f"{PRESET_PFX}{req.name.strip()}", json.dumps(req.params))
    return {"status": "OK"}


@router.delete("/presets/{name}")
async def delete_preset(name: str, _: User = Depends(get_admin_user)):
    _redis().delete(f"{PRESET_PFX}{name}")
    return {"status": "OK"}


# ── A/B History ───────────────────────────────────────────────────────────────
@router.get("/history")
async def get_history(_: User = Depends(get_admin_user)):
    try:
        raw = _redis().get(HISTORY_KEY)
        return json.loads(raw) if raw else []
    except Exception:
        return []


class ABRequest(BaseModel):
    question: str
    params_a: dict
    params_b: dict
    label_a: str = "配置A"
    label_b: str = "配置B"


@router.post("/run-ab")
async def run_ab(req: ABRequest, admin: User = Depends(get_admin_user)):
    from ...core.database import get_driver

    async def _run_one(params: dict) -> dict:
        t0 = time.time()
        try:
            from ...core.database import _driver as drv
            from ..query.core import do_retrieval
            alpha = params.get("alpha", 0.5)
            top_k = int(params.get("top_k", 5))
            # temporarily set alpha
            try:
                _redis().set("search:hybrid_alpha", str(alpha))
            except Exception:
                pass
            sections, _, _ = await asyncio.to_thread(
                do_retrieval, drv, req.question, "parallel", top_k
            )
            return {"score_top1": round(sections[0].get("score", 0), 3) if sections else 0,
                    "count": len(sections), "latency_ms": int((time.time() - t0) * 1000), "error": None}
        except Exception as e:
            return {"score_top1": 0, "count": 0, "latency_ms": int((time.time() - t0) * 1000), "error": str(e)}

    result_a, result_b = await asyncio.gather(_run_one(req.params_a), _run_one(req.params_b))
    # restore current global alpha
    try:
        cur = _get_params()
        _redis().set("search:hybrid_alpha", str(cur.get("alpha", 0.5)))
    except Exception:
        pass

    entry = {
        "ts": int(time.time()), "question": req.question[:80],
        "label_a": req.label_a, "params_a": req.params_a, "result_a": result_a,
        "label_b": req.label_b, "params_b": req.params_b, "result_b": result_b,
        "user": admin.username,
    }
    try:
        r = _redis()
        history = json.loads(r.get(HISTORY_KEY) or "[]")
        history.insert(0, entry)
        r.set(HISTORY_KEY, json.dumps(history[:20]))  # keep last 20
    except Exception:
        pass
    return entry


@router.post("/apply")
async def apply_params(req: ParamsUpdate, _: User = Depends(get_admin_user)):
    await asyncio.to_thread(_set_params, {**_get_params(), **req.params})
    return {"status": "OK", "message": "已应用为全局默认参数"}
