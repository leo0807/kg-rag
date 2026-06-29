"""知识演化时间轴 API — 按天统计知识图谱构建进度"""
from __future__ import annotations
import logging
from fastapi import APIRouter, Depends
from neo4j import Driver
from ...core.database import get_driver

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["timeline"])


def _backfill_created_at(session) -> None:
    session.run("MATCH (d:Document) WHERE d.created_at IS NULL SET d.created_at = datetime()")


@router.get("/timeline")
async def get_timeline(driver: Driver = Depends(get_driver)):
    """每日入库统计：文档、章节、图片、表格数量。
    原 6 次串行 session.run() 合并为 3 次，减少 3 次网络往返。
    """
    with driver.session() as session:
        _backfill_created_at(session)

        day_data: dict[str, dict] = {}

        # ── 查询 1：4 类指标按日汇聚（UNION ALL，1 次代替 4 次）────────────
        for r in session.run("""
            MATCH (d:Document)
            WHERE d.title IS NOT NULL AND d.created_at IS NOT NULL
            RETURN toString(date(d.created_at)) AS day, count(d) AS cnt, 'docs' AS kind
            UNION ALL
            MATCH (d:Document)-[:HAS_SECTION]->(s:Section)
            WHERE d.title IS NOT NULL AND d.created_at IS NOT NULL
            RETURN toString(date(d.created_at)) AS day, count(s) AS cnt, 'sections' AS kind
            UNION ALL
            MATCH (d:Document)-[:HAS_IMAGE]->(i:Image)
            WHERE d.title IS NOT NULL AND d.created_at IS NOT NULL
            RETURN toString(date(d.created_at)) AS day, count(i) AS cnt, 'images' AS kind
            UNION ALL
            MATCH (d:Document)-[:HAS_SECTION]->(s:Section)-[:HAS_TABLE]->(t:Table)
            WHERE d.title IS NOT NULL AND d.created_at IS NOT NULL
            RETURN toString(date(d.created_at)) AS day, count(t) AS cnt, 'tables' AS kind
        """):
            day = r["day"]
            if day not in day_data:
                day_data[day] = {"docs_added": 0, "sections_added": 0,
                                 "images_added": 0, "tables_added": 0}
            kind = r["kind"]
            if kind == "docs":       day_data[day]["docs_added"]     = r["cnt"]
            elif kind == "sections": day_data[day]["sections_added"] = r["cnt"]
            elif kind == "images":   day_data[day]["images_added"]   = r["cnt"]
            elif kind == "tables":   day_data[day]["tables_added"]   = r["cnt"]

        # ── 查询 2：最早/最新文档（ORDER BY + LIMIT，1 次代替 2 次）────────
        first = latest = None
        for r in session.run("""
            MATCH (d:Document)
            WHERE d.title IS NOT NULL AND d.created_at IS NOT NULL
            WITH d ORDER BY d.created_at ASC LIMIT 1
            RETURN d.name AS name, 'first' AS pos
            UNION ALL
            MATCH (d:Document)
            WHERE d.title IS NOT NULL AND d.created_at IS NOT NULL
            WITH d ORDER BY d.created_at DESC LIMIT 1
            RETURN d.name AS name, 'latest' AS pos
        """):
            if r["pos"] == "first":  first  = r
            else:                    latest = r

    daily = [{"date": k, **v} for k, v in sorted(day_data.items())]
    return {
        "daily": daily,
        "total_span_days": len(daily),
        "first_doc": first["name"] if first else "",
        "latest_doc": latest["name"] if latest else "",
    }


@router.get("/timeline/docs")
async def timeline_docs(date: str, driver: Driver = Depends(get_driver)):
    """指定日期入库的文档列表。"""
    with driver.session() as session:
        result = session.run("""
            MATCH (d:Document)
            WHERE d.title IS NOT NULL AND d.created_at IS NOT NULL
              AND toString(date(d.created_at)) = $date
            RETURN d.name AS doc_id, d.title AS title,
                   COALESCE(d.version, '') AS version,
                   size([(d)-[:HAS_SECTION]->() | 1]) AS section_count
            ORDER BY d.name
        """, date=date)
        docs = [
            {"doc_id": r["doc_id"], "title": r["title"],
             "version": r["version"], "section_count": r["section_count"]}
            for r in result
        ]
    return {"date": date, "docs": docs}


@router.get("/timeline/compare")
async def timeline_compare(from_date: str, to_date: str, driver: Driver = Depends(get_driver)):
    """比较两个时间点之间新增的文档与章节。"""
    with driver.session() as session:
        docs_res = session.run("""
            MATCH (d:Document)
            WHERE d.title IS NOT NULL AND d.created_at IS NOT NULL
              AND toString(date(d.created_at)) >= $from_date
              AND toString(date(d.created_at)) <= $to_date
            RETURN d.name AS doc_id, d.title AS title,
                   COALESCE(d.version, '') AS version,
                   toString(date(d.created_at)) AS added_on,
                   size([(d)-[:HAS_SECTION]->() | 1]) AS section_count
            ORDER BY d.created_at
        """, from_date=from_date, to_date=to_date)
        new_docs = [
            {"doc_id": r["doc_id"], "title": r["title"], "version": r["version"],
             "added_on": r["added_on"], "section_count": r["section_count"]}
            for r in docs_res
        ]
        sec_res = session.run("""
            MATCH (d:Document)-[:HAS_SECTION]->(s:Section)
            WHERE d.title IS NOT NULL AND d.created_at IS NOT NULL
              AND toString(date(d.created_at)) >= $from_date
              AND toString(date(d.created_at)) <= $to_date
            RETURN count(s) AS cnt
        """, from_date=from_date, to_date=to_date).single()

    return {
        "from_date": from_date,
        "to_date": to_date,
        "new_docs": new_docs,
        "docs_count": len(new_docs),
        "sections_count": sec_res["cnt"] if sec_res else 0,
    }
