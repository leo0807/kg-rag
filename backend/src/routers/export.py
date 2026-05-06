"""知识资产导出 API"""
from __future__ import annotations
import io, json, logging
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from neo4j import Driver
from ..core.database import get_driver
from ..db.session import get_db
from .export_writers import build_excel, build_graphml, build_markdown
from ..services.pii_masker import pii_masker

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/export", tags=["export"])


class SectionsRequest(BaseModel):
    doc_ids: list[str] = []
    format: str = "json"          # json | markdown | excel
    include_content: bool = True
    mask_pii: bool = True         # 是否脱敏个人信息（推荐保持 True）


class GraphRequest(BaseModel):
    doc_ids: list[str] = []
    format: str = "json"          # json | graphml
    include_nodes: list[str] = ["Document", "Section"]
    include_edges: list[str] = ["HAS_SECTION", "REFERENCES"]


class QAPairsRequest(BaseModel):
    limit: int = 1000
    mask_pii: bool = True


def _doc_filter(alias: str, doc_ids: list[str]) -> str:
    if not doc_ids:
        return ""
    safe = [d for d in doc_ids if d.replace("-", "").replace("_", "").isalnum()]
    if not safe:
        return ""
    ids_str = ", ".join(f'"{d}"' for d in safe)
    return f" AND {alias}.name IN [{ids_str}]"


@router.post("/sections")
async def export_sections(req: SectionsRequest, driver: Driver = Depends(get_driver)):
    doc_filter = _doc_filter("d", req.doc_ids)
    with driver.session() as session:
        docs = [dict(r) for r in session.run(f"""
            MATCH (d:Document) WHERE d.title IS NOT NULL{doc_filter}
            RETURN d.name AS doc_id, d.title AS title, COALESCE(d.version,'') AS version,
                   COALESCE(d.issue_date,'') AS issue_date,
                   size([(d)-[:HAS_SECTION]->() | 1]) AS section_count,
                   size([(d)-[:HAS_IMAGE]->() | 1]) AS image_count
            ORDER BY d.name
        """)]
        content_clause = ", s.content AS content" if req.include_content else ""
        sections = [dict(r) for r in session.run(f"""
            MATCH (d:Document)-[:HAS_SECTION]->(s:Section)
            WHERE d.title IS NOT NULL{doc_filter}
            RETURN d.name AS doc_id, COALESCE(s.number,'') AS number,
                   COALESCE(s.title,'') AS title, COALESCE(s.level,1) AS level{content_clause}
            ORDER BY d.name, s.seq_index
        """)]

    if req.mask_pii:
        sections = [pii_masker.mask_dict(s, ["title", "content"]) for s in sections]

    fmt = req.format.lower()
    if fmt == "excel":
        with driver.session() as session:
            refs = [{"source": r["src"], "target": r["tgt"]} for r in session.run(f"""
                MATCH (d:Document)-[:REFERENCES]->(r:Document)
                WHERE d.title IS NOT NULL{doc_filter}
                RETURN d.name AS src, r.name AS tgt
            """)]
            entities = [dict(r) for r in session.run(f"""
                MATCH (e)-[:MENTIONED_IN]->(s:Section)<-[:HAS_SECTION]-(d:Document)
                WHERE d.title IS NOT NULL{doc_filter}
                  AND (e:Tool OR e:Material OR e:Process OR e:Constraint)
                RETURN COALESCE(e.name,'') AS name, labels(e)[0] AS type,
                       count(s) AS count, count(DISTINCT d) AS doc_count
                ORDER BY count DESC LIMIT 500
            """)]
            for e in entities:
                e["docs"] = str(e.pop("doc_count", 0))
        buf = build_excel(docs, sections, refs, entities)
        return StreamingResponse(buf,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=cps_export.xlsx"})

    if fmt == "markdown":
        md = build_markdown(docs, sections)
        return StreamingResponse(io.BytesIO(md.encode()),
            media_type="text/markdown",
            headers={"Content-Disposition": "attachment; filename=cps_sections.md"})

    # default: json
    payload = json.dumps({"documents": docs, "sections": sections}, ensure_ascii=False, indent=2)
    return StreamingResponse(io.BytesIO(payload.encode()),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=cps_sections.json"})


@router.post("/graph")
async def export_graph(req: GraphRequest, driver: Driver = Depends(get_driver)):
    doc_filter = _doc_filter("d", req.doc_ids)
    with driver.session() as session:
        nodes: list[dict] = []
        edges: list[dict] = []
        for label in req.include_nodes:
            if label == "Document":
                for r in session.run(f"MATCH (d:Document) WHERE d.title IS NOT NULL{doc_filter} RETURN d.name AS id, d.title AS title"):
                    nodes.append({"id": r["id"], "label": "Document", "title": r["title"] or "", "type": "Document"})
            elif label == "Section":
                for r in session.run(f"MATCH (d:Document)-[:HAS_SECTION]->(s:Section) WHERE d.title IS NOT NULL{doc_filter} RETURN s.chunk_id AS id, COALESCE(s.title,'') AS title"):
                    nodes.append({"id": r["id"], "label": "Section", "title": r["title"], "type": "Section"})
        for rel in req.include_edges:
            for r in session.run(f"MATCH (a)-[:{rel}]->(b) WHERE exists(a.name) OR exists(a.chunk_id) RETURN COALESCE(a.name, a.chunk_id) AS src, COALESCE(b.name, b.chunk_id) AS tgt LIMIT 5000"):
                edges.append({"source": r["src"], "target": r["tgt"], "label": rel})

    fmt = req.format.lower()
    if fmt == "graphml":
        xml_str = build_graphml(nodes, edges)
        return StreamingResponse(io.BytesIO(xml_str.encode()),
            media_type="application/xml",
            headers={"Content-Disposition": "attachment; filename=cps_graph.graphml"})

    payload = json.dumps({"nodes": nodes, "edges": edges}, ensure_ascii=False, indent=2)
    return StreamingResponse(io.BytesIO(payload.encode()),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=cps_graph.json"})


@router.post("/qa-pairs")
async def export_qa_pairs(req: QAPairsRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        text("SELECT messages FROM conversations WHERE messages != '[]' ORDER BY updated_at DESC LIMIT :lim"),
        {"lim": req.limit},
    )
    lines: list[str] = []
    for (msgs_json,) in result.fetchall():
        try:
            msgs = json.loads(msgs_json)
        except Exception:
            continue
        for i, msg in enumerate(msgs):
            if msg.get("role") == "user" and i + 1 < len(msgs) and msgs[i + 1].get("role") == "assistant":
                ans = msgs[i + 1]
                if not ans.get("content"):
                    continue
                instruction = msg["content"]
                output = ans["content"]
                if req.mask_pii:
                    instruction = pii_masker.mask(instruction)
                    output      = pii_masker.mask(output)
                record = {"instruction": instruction, "output": output, "context": ""}
                lines.append(json.dumps(record, ensure_ascii=False))
    payload = "\n".join(lines)
    return StreamingResponse(io.BytesIO(payload.encode()),
        media_type="application/jsonl",
        headers={"Content-Disposition": "attachment; filename=cps_qa_pairs.jsonl"})
