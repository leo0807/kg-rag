"""
Blueprint API — 工程图纸解析与标注数据查询。

GET  /api/blueprint/annotations/{image_id}  — 查询已解析标注数据
POST /api/blueprint/parse                   — 上传图纸文件，返回结构化 JSON
"""
from __future__ import annotations

import asyncio
import json
import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from neo4j import Driver

from ..core.database import get_driver
from ..services.images.image_file_service import resolve_image_binary_path
from ..services.vision.blueprint_parser import (
    BlueprintResult,
    parse_blueprint,
    parse_blueprint_from_pdf,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/blueprint", tags=["blueprint"])

_IMAGE_QUERY = """
MATCH (i:Image {image_id: $image_id})
RETURN
  i.path            AS path,
  i.minio_path      AS minio_path,
  i.caption         AS caption,
  i.description     AS description,
  i.is_drawing      AS is_drawing,
  i.part_numbers    AS part_numbers,
  i.annotations     AS annotations,
  i.assembly_relations AS assembly_relations,
  i.summary         AS summary
LIMIT 1
"""


def _load_json_field(raw) -> list:
    if not raw:
        return []
    if isinstance(raw, list):
        return raw
    try:
        val = json.loads(raw)
        return val if isinstance(val, list) else []
    except Exception:
        return []


def _build_blueprint_data_from_neo4j(image_id: str, rec: dict) -> dict:
    """将 Neo4j 已存储的分析结果映射为 BlueprintData 格式。"""
    from ..services.vision.blueprint_parser import (
        _annotations_to_fasteners,
        _annotations_to_dimensions,
        _extract_process_requirements,
    )

    annotations = _load_json_field(rec.get("annotations"))
    part_numbers = _load_json_field(rec.get("part_numbers"))
    summary = rec.get("summary") or rec.get("caption") or rec.get("description") or ""

    parts     = [{"part_no": str(pn)} for pn in part_numbers if pn]
    fasteners = [{"type": f.type, "spec": f.spec} for f in _annotations_to_fasteners(annotations)]
    key_dims  = [
        {"name": d.name, "value": d.value, "unit": d.unit}
        for d in _annotations_to_dimensions(annotations)
    ]
    proc_reqs = _extract_process_requirements(summary, annotations)

    return {
        "drawing_id":           image_id,
        "title":                summary[:60],
        "is_drawing":           bool(rec.get("is_drawing", False)),
        "parts":                parts,
        "fasteners":            fasteners,
        "key_dimensions":       key_dims,
        "process_requirements": proc_reqs,
        "annotations":          annotations,
    }


@router.get("/annotations/{image_id}")
async def get_blueprint_annotations(
    image_id: str,
    driver: Driver = Depends(get_driver),
):
    """返回图纸的结构化标注数据。

    优先使用已缓存在 Neo4j Image 节点上的分析结果；
    若未分析则尝试实时解析（可能较慢）。
    """
    with driver.session() as session:
        rec = session.run(_IMAGE_QUERY, image_id=image_id).single()

    if not rec:
        raise HTTPException(404, f"图片不存在: {image_id}")

    rec = dict(rec)

    # 已缓存分析结果
    if rec.get("annotations") is not None or rec.get("is_drawing") is not None:
        return _build_blueprint_data_from_neo4j(image_id, rec)

    # 尚未分析 — 尝试实时解析
    result = await _parse_image_from_neo4j_rec(image_id, rec)
    if result is None:
        # 无法解析，返回空壳
        return {
            "drawing_id": image_id,
            "title":      rec.get("caption") or image_id,
            "is_drawing": False,
            "parts": [], "fasteners": [], "key_dimensions": [],
            "process_requirements": [], "annotations": [],
        }
    return result.to_dict()


async def _parse_image_from_neo4j_rec(
    image_id: str,
    rec: dict,
) -> BlueprintResult | None:
    cleanup_path: Path | None = None
    try:
        image_path, cleanup_path = resolve_image_binary_path(
            image_id=image_id,
            local_path=rec.get("path"),
            minio_path=rec.get("minio_path"),
        )
    except FileNotFoundError as e:
        logger.warning("无法定位图片文件 %s: %s", image_id, e)
        return None

    caption = rec.get("caption") or rec.get("description") or ""
    try:
        result = await asyncio.to_thread(
            parse_blueprint,
            str(image_path),
            image_id,
            caption,
        )
        return result
    except Exception as e:
        logger.warning("实时图纸解析失败 %s: %s", image_id, e)
        return None
    finally:
        if cleanup_path:
            cleanup_path.unlink(missing_ok=True)


@router.post("/parse")
async def parse_blueprint_upload(
    file: UploadFile = File(...),
    drawing_id: str = Query(default=""),
    doc_id:     str = Query(default=""),
    page_idx:   int = Query(default=0, ge=0),
):
    """上传工程图纸（图片或 PDF），返回结构化解析 JSON。"""
    content_type = file.content_type or ""
    filename     = file.filename or ""
    is_pdf       = content_type == "application/pdf" or filename.lower().endswith(".pdf")

    suffix = ".pdf" if is_pdf else (Path(filename).suffix or ".jpg")
    did    = drawing_id or Path(filename).stem or "upload"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = Path(tmp.name)

    try:
        if is_pdf:
            result = await asyncio.to_thread(
                parse_blueprint_from_pdf, str(tmp_path), page_idx, did, doc_id,
            )
        else:
            result = await asyncio.to_thread(
                parse_blueprint, str(tmp_path), did, "", doc_id,
            )
    except Exception as e:
        logger.error("图纸解析失败 %s: %s", filename, e)
        raise HTTPException(500, f"解析失败: {e}") from e
    finally:
        tmp_path.unlink(missing_ok=True)

    return result.to_dict()
