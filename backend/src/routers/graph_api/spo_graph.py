"""SPO named knowledge graph — generation, retrieval, deletion."""
from __future__ import annotations

import logging
import time

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from neo4j import Driver
from pydantic import BaseModel

from ...auth.deps import get_current_user, get_protected_driver
from ...db.models import User
from ...services.graph.spo_extractor import extract_spo_from_sections
from ...services.graph.spo_writer import (
    create_spo_graph,
    delete_spo_graph,
    ensure_global_graph,
    get_spo_graph_data,
    list_spo_graphs,
    merge_triples_into_graph,
    update_global_graph_counts,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/graph/spo", tags=["spo-graph"])

# In-memory job status (sufficient for single-process dev; swap for Redis in prod)
_jobs: dict[str, dict] = {}


class GenerateRequest(BaseModel):
    doc_id: str
    chapter: str = "2"


def _fetch_chapter_sections(driver: Driver, doc_id: str, chapter: str) -> list[dict]:
    """Query Neo4j for sections. chapter='ALL' fetches the entire document."""
    if chapter.upper() == "ALL":
        with driver.session() as session:
            result = session.run(
                """
                MATCH (d:Document {name: $doc_id})-[:HAS_SECTION]->(s:Section)
                RETURN s.chunk_id AS chunk_id,
                       s.number   AS number,
                       s.title    AS title,
                       s.content  AS content
                ORDER BY s.number
                """,
                doc_id=doc_id,
            )
            return [dict(r) for r in result]
    prefix = chapter.rstrip(".")
    with driver.session() as session:
        result = session.run(
            """
            MATCH (d:Document {name: $doc_id})-[:HAS_SECTION]->(s:Section)
            WHERE s.number = $prefix
               OR s.number STARTS WITH $dot_prefix
            RETURN s.chunk_id AS chunk_id,
                   s.number   AS number,
                   s.title    AS title,
                   s.content  AS content
            ORDER BY s.number
            """,
            doc_id=doc_id, prefix=prefix, dot_prefix=prefix + ".",
        )
        return [dict(r) for r in result]


def _list_all_doc_ids(driver: Driver) -> list[str]:
    with driver.session() as session:
        result = session.run("MATCH (d:Document) RETURN d.name AS doc_id ORDER BY d.name")
        return [r["doc_id"] for r in result]


def _run_generation(graph_id: str, doc_id: str, chapter: str, driver: Driver) -> None:
    """Background task: extract SPO triples and write to Neo4j."""
    _jobs[graph_id] = {"status": "running", "progress": 0, "total": 0, "message": "加载章节数据"}
    try:
        sections = _fetch_chapter_sections(driver, doc_id, chapter)
        if not sections:
            _jobs[graph_id] = {"status": "failed", "message": f"未找到第 {chapter} 章节内容"}
            return

        _jobs[graph_id]["total"] = len(sections)
        _jobs[graph_id]["message"] = f"开始提取 {len(sections)} 个章节的 SPO 三元组"

        def on_progress(done: int, total: int) -> None:
            _jobs[graph_id]["progress"] = done
            _jobs[graph_id]["message"] = f"SPO 提取中 {done}/{total}"

        spo_results = extract_spo_from_sections(sections, on_progress=on_progress)

        _jobs[graph_id]["message"] = "写入 Neo4j 图谱"
        summary = create_spo_graph(driver, graph_id, doc_id, chapter, spo_results)

        _jobs[graph_id] = {
            "status":     "completed",
            "graph_id":   graph_id,
            "node_count": summary["node_count"],
            "edge_count": summary["edge_count"],
            "message":    "完成",
        }
    except Exception as exc:
        logger.exception("SPO 图谱生成失败: %s", exc)
        _jobs[graph_id] = {"status": "failed", "message": str(exc)}


def _run_all_docs_generation(batch_job_id: str, driver: Driver) -> None:
    """Background task: generate full-doc SPO graphs for every Document in Neo4j."""
    doc_ids = _list_all_doc_ids(driver)
    if not doc_ids:
        _jobs[batch_job_id] = {"status": "failed", "message": "数据库中没有文档"}
        return
    _jobs[batch_job_id] = {
        "status": "running", "progress": 0, "total": len(doc_ids),
        "message": f"批量处理 {len(doc_ids)} 个文档",
    }
    generated: list[str] = []
    for i, doc_id in enumerate(doc_ids):
        graph_id = f"spo_full_{doc_id}_{int(time.time())}"
        _jobs[batch_job_id]["message"] = f"处理 {doc_id} ({i + 1}/{len(doc_ids)})"
        try:
            _run_generation(graph_id, doc_id, "ALL", driver)
        except Exception as exc:
            logger.error("批量生成 %s 失败: %s", doc_id, exc)
        generated.append(graph_id)
        _jobs[batch_job_id]["progress"] = i + 1
    _jobs[batch_job_id] = {
        "status": "completed", "progress": len(doc_ids), "total": len(doc_ids),
        "generated": generated, "message": f"完成，共 {len(generated)} 张图谱",
    }


class GlobalGenerateRequest(BaseModel):
    graph_id: str = "spo_global"
    max_sections: int = 200
    min_len: int = 150


def _run_global_generation(
    job_id: str, max_sections: int, min_len: int, graph_id: str, driver: Driver
) -> None:
    """Background task: incrementally build/extend the spo_global graph."""
    _jobs[job_id] = {"status": "running", "progress": 0, "total": 0, "message": "加载章节"}
    try:
        with driver.session() as s:
            rows = s.run(
                """
                MATCH (d:Document)-[:HAS_SECTION]->(sec:Section)
                WHERE sec.content IS NOT NULL AND size(trim(sec.content)) >= $min_len
                RETURN sec.chunk_id AS chunk_id, sec.number AS number,
                       sec.title AS title, sec.content AS content
                ORDER BY size(trim(sec.content)) DESC
                LIMIT $limit
                """,
                min_len=min_len, limit=max_sections,
            )
            sections = [dict(r) for r in rows]

        ensure_global_graph(driver, graph_id)
        total = len(sections)
        _jobs[job_id].update({"total": total, "message": f"开始提取 {total} 节 SPO"})

        total_triples = 0
        for i, sec in enumerate(sections):
            _jobs[job_id].update({"progress": i, "message": f"提取中 {i + 1}/{total} | 已得 {total_triples} 条"})
            spo_results = extract_spo_from_sections([sec], batch_size=1)
            if spo_results:
                total_triples += merge_triples_into_graph(driver, graph_id, spo_results)

        update_global_graph_counts(driver, graph_id)
        _jobs[job_id] = {
            "status": "completed", "progress": total, "total": total,
            "graph_id": graph_id, "triple_count": total_triples, "message": "完成",
        }
    except Exception as exc:
        logger.exception("全局图谱生成失败: %s", exc)
        _jobs[job_id] = {"status": "failed", "message": str(exc)}


@router.post("/generate-global")
async def generate_global_graph(
    req: GlobalGenerateRequest,
    background_tasks: BackgroundTasks,
    _: User = Depends(get_current_user),
    driver: Driver = Depends(get_protected_driver),
):
    """Incrementally build the spo_global graph from the richest sections."""
    job_id = f"global_{req.graph_id}_{int(time.time())}"
    _jobs[job_id] = {"status": "pending", "message": "排队中"}
    background_tasks.add_task(
        _run_global_generation, job_id, req.max_sections, req.min_len, req.graph_id, driver
    )
    return {"job_id": job_id, "graph_id": req.graph_id, "status": "started"}


@router.post("/generate-all-docs")
async def generate_all_docs(
    background_tasks: BackgroundTasks,
    _: User = Depends(get_current_user),
    driver: Driver = Depends(get_protected_driver),
):
    """Start full-doc SPO generation for every document in Neo4j."""
    batch_job_id = f"batch_all_{int(time.time())}"
    _jobs[batch_job_id] = {"status": "pending", "message": "排队中"}
    background_tasks.add_task(_run_all_docs_generation, batch_job_id, driver)
    return {"job_id": batch_job_id, "status": "started"}


@router.post("/generate")
async def generate_spo_graph(
    req: GenerateRequest,
    background_tasks: BackgroundTasks,
    _: User = Depends(get_current_user),
    driver: Driver = Depends(get_protected_driver),
):
    """Start SPO graph generation for a chapter in background."""
    graph_id = f"spo_ch{req.chapter}_{req.doc_id}_{int(time.time())}"
    _jobs[graph_id] = {"status": "pending", "message": "排队中"}
    background_tasks.add_task(_run_generation, graph_id, req.doc_id, req.chapter, driver)
    return {"graph_id": graph_id, "status": "started"}


@router.get("/jobs/{graph_id}")
async def get_job_status(
    graph_id: str,
    _: User = Depends(get_current_user),
):
    """Poll generation job status."""
    job = _jobs.get(graph_id)
    if job is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return job


@router.get("/list")
async def list_graphs(
    _: User = Depends(get_current_user),
    driver: Driver = Depends(get_protected_driver),
):
    """List all named SPO knowledge graphs."""
    return list_spo_graphs(driver)


@router.get("/{graph_id}")
async def get_graph(
    graph_id: str,
    _: User = Depends(get_current_user),
    driver: Driver = Depends(get_protected_driver),
):
    """Get all nodes and edges of a named SPO graph for visualization."""
    data = get_spo_graph_data(driver, graph_id)
    if data["graph"] is None:
        raise HTTPException(status_code=404, detail="图谱不存在")
    return data


@router.delete("/{graph_id}")
async def delete_graph(
    graph_id: str,
    _: User = Depends(get_current_user),
    driver: Driver = Depends(get_protected_driver),
):
    """Delete a named SPO knowledge graph."""
    cnt = delete_spo_graph(driver, graph_id)
    _jobs.pop(graph_id, None)
    return {"deleted_nodes": cnt}
