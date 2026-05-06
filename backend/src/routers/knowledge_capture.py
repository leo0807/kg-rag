"""对话上下文知识捕获 — LLM 三元组抽取 + Neo4j 写入"""
from __future__ import annotations
import json, asyncio, logging
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from neo4j import Driver
from ..core.database import get_driver
from ..auth.deps import get_current_user
from ..db.models import User
from ..services.ai.llm_service import get_llm_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/knowledge", tags=["knowledge-capture"])

_EXTRACT_PROMPT = """你是知识图谱专家。从给定文本中抽取三元组（主体-谓词-客体），返回 JSON 数组：
[{"subject": "...", "predicate": "...", "object": "..."}, ...]
只返回 JSON，不要其他内容。最多返回 10 个最重要的三元组。若无可抽取内容，返回空数组 []。"""


class Triple(BaseModel):
    subject: str
    predicate: str
    object: str


class ExtractRequest(BaseModel):
    text: str


class CaptureRequest(BaseModel):
    triples: list[Triple]


@router.post("/extract")
async def extract_triples(req: ExtractRequest, _: User = Depends(get_current_user)):
    llm = get_llm_service()

    def _call():
        return llm.chat([{"role": "user", "content": req.text[:3000]}], system_prompt=_EXTRACT_PROMPT)

    try:
        raw = await asyncio.to_thread(_call)
        # Strip markdown code fences if present
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        triples = json.loads(text.strip())
        return {"triples": triples[:10]}
    except Exception as e:
        logger.warning("Triple extraction failed: %s", e)
        return {"triples": []}


@router.post("/capture")
async def capture_triples(
    req: CaptureRequest,
    driver: Driver = Depends(get_driver),
    user: User = Depends(get_current_user),
):
    if not req.triples:
        return {"status": "OK", "created": 0}

    def _write():
        with driver.session() as s:
            for t in req.triples:
                rel = t.predicate.upper().replace(" ", "_").replace("-", "_")[:50] or "RELATED_TO"
                if not rel.replace("_", "").isalnum():
                    rel = "RELATED_TO"
                s.run(
                    f"MERGE (a {{name: $subj}}) "
                    f"ON CREATE SET a.source = 'user_annotation', a.created_by = $uid "
                    f"MERGE (b {{name: $obj}}) "
                    f"ON CREATE SET b.source = 'user_annotation', b.created_by = $uid "
                    f"MERGE (a)-[r:{rel}]->(b) "
                    f"ON CREATE SET r.source = 'user_annotation', r.created_by = $uid",
                    subj=t.subject, obj=t.object, uid=user.id,
                )
        return len(req.triples)

    created = await asyncio.to_thread(_write)
    return {"status": "OK", "created": created}


@router.get("/annotations")
async def get_annotations(driver: Driver = Depends(get_driver), _: User = Depends(get_current_user)):
    def _fetch():
        with driver.session() as s:
            rows = s.run("MATCH (n {source: 'user_annotation'}) RETURN n.name AS name")
            return [r["name"] for r in rows if r["name"]]

    names = await asyncio.to_thread(_fetch)
    return {"nodes": names}
