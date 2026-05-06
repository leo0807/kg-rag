"""Admin-only Cypher executor — read-only with safety checks."""
from __future__ import annotations
import asyncio
import logging
import re
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from neo4j import Driver
from ...core.database import get_driver
from ...auth.deps import get_admin_user
from ...db.models import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/cypher", tags=["admin-cypher"])

FORBIDDEN = re.compile(r"\b(CREATE|DELETE|SET|MERGE|REMOVE|DROP|DETACH)\b", re.IGNORECASE)
MAX_ROWS = 100
TIMEOUT_S = 10


class CypherRequest(BaseModel):
    query: str
    params: dict = {}


def _to_json(v):
    """Convert Neo4j objects to JSON-serializable types."""
    if hasattr(v, "_properties"):        # Node
        return {"_labels": list(v.labels), **{k: _to_json(val) for k, val in v._properties.items()}}
    if hasattr(v, "_type"):              # Relationship
        return {"_type": v._type, **{k: _to_json(val) for k, val in v._properties.items()}}
    if isinstance(v, (list, tuple)):
        return [_to_json(i) for i in v]
    return v


@router.post("/execute")
async def execute_cypher(
    req: CypherRequest,
    _: User = Depends(get_admin_user),
    driver: Driver = Depends(get_driver),
):
    if FORBIDDEN.search(req.query):
        return {"error": "禁止写操作（CREATE/DELETE/SET/MERGE/REMOVE/DROP）", "rows": [], "columns": []}

    def _run():
        with driver.session() as s:
            res = s.run(req.query, req.params)
            keys = list(res.keys())
            rows: list[dict] = []
            for rec in res:
                rows.append({k: _to_json(rec[k]) for k in keys})
                if len(rows) >= MAX_ROWS:
                    break
            return keys, rows

    try:
        keys, rows = await asyncio.wait_for(asyncio.to_thread(_run), timeout=float(TIMEOUT_S))
        return {"columns": keys, "rows": rows, "total": len(rows), "error": None}
    except asyncio.TimeoutError:
        return {"error": f"查询超时（{TIMEOUT_S} 秒）", "rows": [], "columns": []}
    except Exception as e:
        logger.warning("Cypher execute error: %s", e)
        return {"error": str(e), "rows": [], "columns": []}
