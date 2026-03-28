"""
src/routers/sessions.py
查询会话管理
"""
import logging
from fastapi import APIRouter, Depends
from neo4j import Driver
from pydantic import BaseModel
from ..core.database import get_driver

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["sessions"])


class SessionCreate(BaseModel):
    id:       str
    question: str
    answer:   str
    sources:  list[dict]


@router.get("/sessions")
async def list_sessions(driver: Driver = Depends(get_driver)):
    with driver.session() as session:
        result = session.run("""
            MATCH (s:QuerySession)
            RETURN s.id        AS id,
                   s.question  AS question,
                   s.answer    AS answer,
                   s.sources   AS sources,
                   s.timestamp AS timestamp
            ORDER BY s.timestamp DESC
            LIMIT 20
        """)
        return [dict(r) for r in result]


@router.post("/sessions")
async def create_session(
    req:    SessionCreate,
    driver: Driver = Depends(get_driver),
):
    import json, time
    with driver.session() as session:
        session.run("""
            MERGE (s:QuerySession {id: $id})
            SET s.question  = $question,
                s.answer    = $answer,
                s.sources   = $sources,
                s.timestamp = $timestamp
        """,
        id=req.id,
        question=req.question,
        answer=req.answer,
        sources=json.dumps(req.sources, ensure_ascii=False),
        timestamp=int(time.time() * 1000),
        )
    return {"status": "OK"}


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    driver:     Driver = Depends(get_driver),
):
    with driver.session() as session:
        session.run("""
            MATCH (s:QuerySession {id: $id})
            DELETE s
        """, id=session_id)
    return {"status": "OK"}