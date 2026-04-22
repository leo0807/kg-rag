"""
src/routers/documents_entities.py
文档实体与图片相关 API
"""
import asyncio
import json
import logging
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from neo4j import Driver
from ..core.database import get_driver

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["documents"])

_DOCUMENT_IMAGES_MATCH = """
    MATCH (d:Document {name: $doc_id})
    OPTIONAL MATCH (d)-[:HAS_SECTION]->(:Section)-[:HAS_IMAGE]->(section_img:Image)
    WITH d, collect(DISTINCT section_img) AS section_imgs
    OPTIONAL MATCH (d)-[:HAS_IMAGE]->(doc_img:Image)
    WITH section_imgs + collect(DISTINCT doc_img) AS all_imgs
    UNWIND all_imgs AS img
    WITH DISTINCT img
    WHERE img IS NOT NULL
"""


def _decode_json_list(raw):
    if isinstance(raw, str):
        try:
            value = json.loads(raw)
        except Exception:
            return []
        return value if isinstance(value, list) else []
    if raw is None:
        return []
    return raw if isinstance(raw, list) else []


@router.get("/images/{image_id}")
async def proxy_image(image_id: str, driver: Driver = Depends(get_driver)):
    """
    图片代理：通过 image_id 从 MinIO 下载图片并直接返回字节流。
    避免前端直接访问 MinIO 内网地址（localhost:9000）产生的 CORS/网络问题。
    """
    with driver.session() as session:
        rec = session.run(
            "MATCH (i:Image {image_id: $iid}) RETURN i.minio_path AS mp LIMIT 1",
            iid=image_id,
        ).single()
    if not rec or not rec["mp"]:
        raise HTTPException(404, f"图片不存在或无 MinIO 路径: {image_id}")

    minio_path = rec["mp"]
    try:
        from ..core.storage import download_bytes, BUCKET_EXTRACTED_IMAGES
        data = download_bytes(BUCKET_EXTRACTED_IMAGES, minio_path)
    except Exception as e:
        logger.warning("图片代理下载失败 %s: %s", minio_path, e)
        raise HTTPException(502, "图片下载失败")

    # 根据扩展名推断 Content-Type
    ext = minio_path.rsplit(".", 1)[-1].lower()
    content_type = {
        "jpg": "image/jpeg", "jpeg": "image/jpeg",
        "png": "image/png", "gif": "image/gif",
        "webp": "image/webp",
    }.get(ext, "image/jpeg")

    return Response(
        content=data,
        media_type=content_type,
        headers={"Cache-Control": "max-age=3600, immutable"},
    )


@router.get("/images/{image_id}/detail")
async def get_image_detail(image_id: str, driver: Driver = Depends(get_driver)):
    """返回图片完整元数据，含所属章节信息。"""
    with driver.session() as session:
        rec = session.run("""
            MATCH (i:Image {image_id: $iid})
            OPTIONAL MATCH (s:Section)-[:HAS_IMAGE]->(i)
            RETURN
                i.image_id        AS image_id,
                i.doc_id          AS doc_id,
                i.caption         AS caption,
                i.description     AS description,
                i.is_drawing      AS is_drawing,
                i.minio_path      AS minio_path,
                i.drawing_summary AS drawing_summary,
                i.part_numbers    AS part_numbers,
                i.annotations     AS annotations,
                i.assembly_relations AS assembly_relations,
                i.keywords        AS keywords,
                i.page            AS page,
                s.chunk_id        AS section_chunk_id,
                s.number          AS section_number,
                s.title           AS section_title
            LIMIT 1
        """, iid=image_id).single()
    if not rec:
        raise HTTPException(404, f"图片不存在: {image_id}")
    row = dict(rec)
    for field in ("part_numbers", "annotations", "assembly_relations"):
        row[field] = _decode_json_list(row.get(field))
    mp = row.get("minio_path") or ""
    row["url"] = f"/api/images/{image_id}" if mp else None
    row["analyzed"] = bool(row.get("caption") or row.get("description"))
    row["annotations_count"] = len(row["annotations"])
    return row


@router.get("/documents/{doc_id}/entities")
async def get_document_entities(doc_id: str, driver: Driver = Depends(get_driver)):
    """列出文档中所有工具/材料/工序节点"""
    with driver.session() as session:
        result = session.run("""
            MATCH (d:Document {name: $doc_id})-[:HAS_SECTION]->(s:Section)
            MATCH (s)-[r]->(e)
            WHERE e:Tool OR e:Material OR e:Process
            RETURN DISTINCT
                labels(e)[0]  AS type,
                e.name        AS name,
                type(r)       AS relation,
                s.chunk_id    AS section_chunk_id,
                s.number      AS section_number,
                s.title       AS section_title
            ORDER BY type, name
        """, doc_id=doc_id)
        entities = [dict(r) for r in result]
    return {"doc_id": doc_id, "entities": entities, "total": len(entities)}


@router.get("/entities")
async def search_entities(
    type:     str    = "",
    q:        str    = "",
    page:     int    = 1,
    per_page: int    = 50,
    driver:   Driver = Depends(get_driver),
):
    """实体搜索与过滤，支持分页。type: Tool|Material|Process，q: 名称关键词"""
    valid_types = {"Tool", "Material", "Process"}
    node_label  = type if type in valid_types else None
    per_page    = min(max(per_page, 1), 200)
    skip        = (page - 1) * per_page

    with driver.session() as session:
        if node_label:
            q_where = "($q = '' OR toLower(e.name) CONTAINS toLower($q))"
            cnt = session.run(
                f"MATCH (e:{node_label}) WHERE {q_where} RETURN count(e) AS total", q=q
            ).single()
            total = cnt["total"] if cnt else 0
            result = session.run(
                f"MATCH (e:{node_label}) WHERE {q_where} "
                "RETURN labels(e)[0] AS type, e.name AS name, e.doc_id AS doc_id "
                "ORDER BY e.name SKIP $skip LIMIT $per_page",
                q=q, skip=skip, per_page=per_page,
            )
        else:
            q_where = "(e:Tool OR e:Material OR e:Process) AND ($q = '' OR toLower(e.name) CONTAINS toLower($q))"
            cnt = session.run(
                f"MATCH (e) WHERE {q_where} RETURN count(e) AS total", q=q
            ).single()
            total = cnt["total"] if cnt else 0
            result = session.run(
                f"MATCH (e) WHERE {q_where} "
                "RETURN labels(e)[0] AS type, e.name AS name, e.doc_id AS doc_id "
                "ORDER BY labels(e)[0], e.name SKIP $skip LIMIT $per_page",
                q=q, skip=skip, per_page=per_page,
            )
        entities = [dict(r) for r in result]
    return {
        "entities": entities,
        "total":    total,
        "page":     page,
        "per_page": per_page,
        "pages":    max(1, -(-total // per_page)),
    }


@router.get("/documents/{doc_id}/images")
async def get_document_images(
    doc_id: str,
    page: int = 1,
    per_page: int = 0,
    drawing_only: bool = False,
    driver: Driver = Depends(get_driver),
):
    """列出文档图片，支持按工程图纸过滤与分页。"""
    page = max(page, 1)
    per_page = min(max(per_page, 0), 500)
    skip = (page - 1) * per_page if per_page else 0

    with driver.session() as session:
        counts = session.run(
            _DOCUMENT_IMAGES_MATCH
            + """
            RETURN
                count(img) AS total,
                sum(CASE WHEN coalesce(img.is_drawing, false) THEN 1 ELSE 0 END) AS drawing_total
            """,
            doc_id=doc_id,
        ).single()

        pagination_clause = ""
        if per_page:
            pagination_clause = "\n            SKIP $skip LIMIT $per_page"

        result = session.run(
            _DOCUMENT_IMAGES_MATCH
            + """
            WITH img
            WHERE ($drawing_only = false OR coalesce(img.is_drawing, false))
            OPTIONAL MATCH (s:Section)-[:HAS_IMAGE]->(img)
            WITH
                img,
                head(collect(DISTINCT s.chunk_id)) AS section_chunk_id,
                head(collect(DISTINCT s.number)) AS section_number,
                head(collect(DISTINCT s.title)) AS section_title
            RETURN
                img.image_id            AS image_id,
                img.caption             AS caption,
                img.path                AS path,
                img.minio_path          AS minio_path,
                img.description         AS description,
                img.is_drawing          AS is_drawing,
                img.part_numbers        AS part_numbers,
                img.annotations         AS annotations,
                img.assembly_relations  AS assembly_relations,
                img.drawing_summary     AS drawing_summary,
                section_chunk_id        AS section_chunk_id,
                section_number          AS section_number,
                section_title           AS section_title
            ORDER BY coalesce(img.page, 0), image_id
            """
            + pagination_clause,
            doc_id=doc_id,
            drawing_only=drawing_only,
            skip=skip,
            per_page=per_page,
        )
        images = []
        for r in result:
            row = dict(r)
            # JSON 字段反序列化
            for field in ("part_numbers", "annotations", "assembly_relations"):
                row[field] = _decode_json_list(row.get(field))
            # 使用代理接口 URL，避免直连 MinIO 的 CORS/内网问题
            image_id = row.get("image_id") or ""
            minio_path = row.get("minio_path") or ""
            row["url"] = f"/api/images/{image_id}" if image_id and minio_path else None
            row["annotations_count"] = len(row["annotations"])
            images.append(row)

    counts_row = dict(counts) if counts else {}
    total = int(counts_row.get("total") or 0)
    drawing_total = int(counts_row.get("drawing_total") or 0)
    filtered_total = drawing_total if drawing_only else total
    has_more = bool(per_page and (skip + len(images) < filtered_total))
    effective_per_page = per_page or len(images)

    return {
        "doc_id": doc_id,
        "images": images,
        "total": total,
        "drawing_total": drawing_total,
        "filtered_total": filtered_total,
        "page": page,
        "per_page": effective_per_page,
        "has_more": has_more,
    }


@router.post("/documents/{doc_id}/images/{image_id}/analyze-drawing")
async def analyze_drawing_endpoint(
    doc_id:   str,
    image_id: str,
    driver:   Driver = Depends(get_driver),
):
    """对指定图片发起（重新）工程图纸专项分析，结果写入 Neo4j。"""
    import json as _json

    with driver.session() as session:
        rec = session.run(
            "MATCH (i:Image {image_id: $image_id}) RETURN i.path AS path, i.caption AS caption LIMIT 1",
            image_id=image_id,
        ).single()
    if not rec:
        raise HTTPException(404, f"图片不存在: {image_id}")

    async def _run():
        try:
            from ..services.drawing_analyzer import analyze_drawing
            from ..services.entity_writer    import write_drawing_constraints
            result = analyze_drawing(rec["path"], rec["caption"] or "", doc_id)
            with driver.session() as session:
                session.run("""
                    MATCH (i:Image {image_id: $image_id})
                    SET i.is_drawing         = $is_drawing,
                        i.part_numbers       = $part_numbers,
                        i.annotations        = $annotations,
                        i.assembly_relations = $assembly_relations,
                        i.drawing_summary    = $summary
                """,
                    image_id          = image_id,
                    is_drawing        = result.get("is_drawing", False),
                    part_numbers      = _json.dumps(result.get("part_numbers", []), ensure_ascii=False),
                    annotations       = _json.dumps(result.get("annotations", []), ensure_ascii=False),
                    assembly_relations= _json.dumps(result.get("assembly_relations", []), ensure_ascii=False),
                    summary           = result.get("summary", ""),
                )
            if result.get("annotations"):
                write_drawing_constraints(driver, image_id, doc_id, result["annotations"])
            logger.info("图纸重新分析完成 image_id=%s", image_id)
        except Exception as e:
            logger.warning("图纸重新分析失败 image_id=%s: %s", image_id, e)

    asyncio.create_task(_run())
    return {"image_id": image_id, "status": "analyzing", "message": "图纸分析已在后台启动"}


@router.post("/documents/{doc_id}/reanalyze")
async def reanalyze_document(doc_id: str, driver: Driver = Depends(get_driver)):
    """
    对已入库文档重新提取实体/图片分析（用于模型升级后）。
    实际分析在后台运行，立即返回任务状态。
    """
    with driver.session() as session:
        doc = session.run(
            "MATCH (d:Document {name: $doc_id}) RETURN d LIMIT 1", doc_id=doc_id
        ).single()
        if not doc:
            raise HTTPException(404, f"文档不存在: {doc_id}")

    async def _reanalyze():
        try:
            from ..services.entity_extractor import extract_entities_from_sections
            from ..services.entity_writer    import write_entities
            with driver.session() as session:
                sec_result = session.run("""
                    MATCH (d:Document {name: $doc_id})-[:HAS_SECTION]->(s:Section)
                    RETURN s.chunk_id AS chunk_id,
                           s.title   AS title,
                           s.content AS content
                """, doc_id=doc_id)
                sections = [dict(r) for r in sec_result]
            if sections:
                entities = extract_entities_from_sections(sections)
                if entities:
                    write_entities(driver, entities, doc_id)
                    logger.info("文档 %s 实体重新提取完成: %d 个", doc_id, len(entities))
        except Exception as e:
            logger.warning("文档 %s 重新分析失败: %s", doc_id, e)

    asyncio.create_task(_reanalyze())
    return {"doc_id": doc_id, "status": "reanalyze_started", "message": "重新分析已在后台启动"}


@router.get("/documents/{doc_id}/tables")
async def get_document_tables(doc_id: str, driver: Driver = Depends(get_driver)):
    """查询从表格中提取的约束节点（source='table'）"""
    with driver.session() as session:
        result = session.run("""
            MATCH (s:Section {doc_id: $doc_id})-[:HAS_CONSTRAINT]->(c:Constraint {source: 'table'})
            RETURN c.constraint_id AS constraint_id,
                   c.type         AS type,
                   c.description  AS description,
                   c.value        AS value,
                   c.value_min    AS value_min,
                   c.value_max    AS value_max,
                   c.unit         AS unit,
                   s.chunk_id     AS chunk_id,
                   s.number       AS section_number,
                   s.title        AS section_title
            ORDER BY s.number, c.type
        """, doc_id=doc_id)
        constraints = [dict(r) for r in result]
    return {"doc_id": doc_id, "constraints": constraints, "total": len(constraints)}
