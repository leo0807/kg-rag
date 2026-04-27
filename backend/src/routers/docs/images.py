"""
文档图片相关 API（代理、详情、列表、图纸分析）
"""
import asyncio
import json
import logging
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from neo4j import Driver
from ...core.database import get_driver
from ...services.images.image_file_service import resolve_image_binary_path

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["documents"])

_DOCUMENT_IMAGES_MATCH = """
    MATCH (d:Document {name: $doc_id})
    OPTIONAL MATCH (d)-[:HAS_SECTION]->(:Section)-[:HAS_IMAGE]->(section_img:Image)
    WITH d, collect(DISTINCT section_img) AS section_imgs
    OPTIONAL MATCH (d)-[:HAS_IMAGE]->(doc_img:Image)
    WITH section_imgs, collect(DISTINCT doc_img) AS doc_imgs
    WITH section_imgs + doc_imgs AS all_imgs
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
    with driver.session() as session:
        rec = session.run(
            "MATCH (i:Image {image_id: $iid}) RETURN i.minio_path AS mp LIMIT 1",
            iid=image_id,
        ).single()
    if not rec or not rec["mp"]:
        raise HTTPException(404, f"图片不存在或无 MinIO 路径: {image_id}")
    minio_path = rec["mp"]
    try:
        from ...core.storage import download_bytes, BUCKET_EXTRACTED_IMAGES
        data = download_bytes(BUCKET_EXTRACTED_IMAGES, minio_path)
    except Exception as e:
        logger.warning("图片代理下载失败 %s: %s", minio_path, e)
        raise HTTPException(502, "图片下载失败")
    ext = minio_path.rsplit(".", 1)[-1].lower()
    content_type = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
                    "gif": "image/gif", "webp": "image/webp"}.get(ext, "image/jpeg")
    return Response(content=data, media_type=content_type,
                    headers={"Cache-Control": "max-age=3600, immutable"})


@router.get("/images/{image_id}/detail")
async def get_image_detail(image_id: str, driver: Driver = Depends(get_driver)):
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
                coalesce(i.page_num, i.page, 0) AS page,
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


@router.get("/documents/{doc_id}/images")
async def get_document_images(
    doc_id: str, page: int = 1, per_page: int = 0,
    drawing_only: bool = False, driver: Driver = Depends(get_driver),
):
    page = max(page, 1)
    per_page = min(max(per_page, 0), 500)
    skip = (page - 1) * per_page if per_page else 0

    with driver.session() as session:
        counts = session.run(
            _DOCUMENT_IMAGES_MATCH +
            "RETURN count(img) AS total, sum(CASE WHEN coalesce(img.is_drawing, false) THEN 1 ELSE 0 END) AS drawing_total",
            doc_id=doc_id,
        ).single()
        pagination_clause = "\n            SKIP $skip LIMIT $per_page" if per_page else ""
        result = session.run(
            _DOCUMENT_IMAGES_MATCH + """
            WITH img
            WHERE ($drawing_only = false OR coalesce(img.is_drawing, false))
            OPTIONAL MATCH (s:Section)-[:HAS_IMAGE]->(img)
            WITH img,
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
                section_chunk_id, section_number, section_title
            ORDER BY coalesce(img.page_num, img.page, 0), image_id
            """ + pagination_clause,
            doc_id=doc_id, drawing_only=drawing_only, skip=skip, per_page=per_page,
        )
        images = []
        for r in result:
            row = dict(r)
            for field in ("part_numbers", "annotations", "assembly_relations"):
                row[field] = _decode_json_list(row.get(field))
            iid = row.get("image_id") or ""
            minio_path = row.get("minio_path") or ""
            row["url"] = f"/api/images/{iid}" if iid and minio_path else None
            row["annotations_count"] = len(row["annotations"])
            images.append(row)

    counts_row = dict(counts) if counts else {}
    total = int(counts_row.get("total") or 0)
    drawing_total = int(counts_row.get("drawing_total") or 0)
    filtered_total = drawing_total if drawing_only else total
    has_more = bool(per_page and (skip + len(images) < filtered_total))
    return {
        "doc_id": doc_id, "images": images, "total": total,
        "drawing_total": drawing_total, "filtered_total": filtered_total,
        "page": page, "per_page": per_page or len(images), "has_more": has_more,
    }


@router.post("/documents/{doc_id}/images/{image_id}/analyze-drawing")
async def analyze_drawing_endpoint(doc_id: str, image_id: str, driver: Driver = Depends(get_driver)):
    import json as _json
    with driver.session() as session:
        rec = session.run(
            "MATCH (i:Image {image_id: $image_id}) RETURN i.path AS path, i.minio_path AS minio_path, i.caption AS caption LIMIT 1",
            image_id=image_id,
        ).single()
    if not rec:
        raise HTTPException(404, f"图片不存在: {image_id}")

    async def _run():
        cleanup_path: Path | None = None
        try:
            from ...services.images.drawing_analyzer import analyze_drawing
            from ...services.graph.entity_writer    import write_drawing_constraints
            image_path, cleanup_path = resolve_image_binary_path(
                image_id=image_id, local_path=rec["path"], minio_path=rec["minio_path"])
            result = analyze_drawing(str(image_path), rec["caption"] or "", doc_id)
            with driver.session() as session:
                session.run(
                    "MATCH (i:Image {image_id: $image_id}) "
                    "SET i.is_drawing=$is_drawing, i.part_numbers=$part_numbers, "
                    "i.annotations=$annotations, i.assembly_relations=$assembly_relations, "
                    "i.drawing_summary=$summary",
                    image_id=image_id,
                    is_drawing=result.get("is_drawing", False),
                    part_numbers=_json.dumps(result.get("part_numbers", []), ensure_ascii=False),
                    annotations=_json.dumps(result.get("annotations", []), ensure_ascii=False),
                    assembly_relations=_json.dumps(result.get("assembly_relations", []), ensure_ascii=False),
                    summary=result.get("summary", ""),
                )
            if result.get("annotations"):
                write_drawing_constraints(driver, image_id, doc_id, result["annotations"])
        except Exception as e:
            logger.warning("图纸重新分析失败 image_id=%s: %s", image_id, e)
        finally:
            if cleanup_path:
                cleanup_path.unlink(missing_ok=True)

    asyncio.create_task(_run())
    return {"image_id": image_id, "status": "analyzing", "message": "图纸分析已在后台启动"}
