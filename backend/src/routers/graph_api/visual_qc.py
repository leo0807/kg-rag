"""
视觉质量检测 API — Visual QC AI

POST /api/qc/detect          单张图片缺陷检测（上传文件）
POST /api/qc/detect-image    已入库图片（by image_id）的缺陷检测
GET  /api/qc/defects         查询已写入的缺陷记录
GET  /api/qc/hazards         查询缺陷对应的 Hazard / 整改建议
"""
import logging
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from neo4j import Driver

from ...core.database import get_driver

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/qc", tags=["visual-qc"])

UPLOAD_DIR = Path("uploads/qc")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# ── 辅助 ──────────────────────────────────────────────────────────────────────

def _run_detection(image_path: str, doc_id: str) -> list[dict]:
    """尝试 YOLO 检测，fallback 到 VLM 检测"""
    from ...services.defect_detector import (
        detect_defects, detect_defects_vlm, is_available,
    )
    if is_available():
        defects = detect_defects(image_path)
        if defects:
            return defects
    # YOLO 无结果或不可用时用 VLM
    return detect_defects_vlm(image_path, doc_id)


# ── 端点 ──────────────────────────────────────────────────────────────────────

@router.post("/detect")
async def detect_upload(
    file:     UploadFile = File(...),
    doc_id:   str        = "",
    image_id: str        = "",
    driver:   Driver     = Depends(get_driver),
):
    """
    上传工件图片，运行缺陷检测并将结果写入图谱。
    若提供 image_id 则关联到已有 Image 节点。
    """
    tmp_path = UPLOAD_DIR / file.filename
    with tmp_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    defects = _run_detection(str(tmp_path), doc_id)

    defect_ids = []
    if defects and image_id:
        from ...services.defect_writer import write_defects_batch
        defect_ids = write_defects_batch(driver, image_id, doc_id, defects)

    return {
        "image": file.filename,
        "defects": defects,
        "defect_ids": defect_ids,
        "total": len(defects),
    }


@router.post("/detect-image/{image_id}")
async def detect_existing_image(
    image_id: str,
    driver:   Driver = Depends(get_driver),
):
    """对已入库的 Image 节点重新运行缺陷检测"""
    with driver.session() as session:
        rec = session.run(
            "MATCH (i:Image {image_id: $image_id}) RETURN i.path AS path, i.doc_id AS doc_id LIMIT 1",
            image_id=image_id,
        ).single()
    if not rec:
        raise HTTPException(404, f"图片不存在: {image_id}")

    doc_id = rec["doc_id"] or ""
    defects = _run_detection(rec["path"], doc_id)

    defect_ids = []
    if defects:
        from ...services.defect_writer import write_defects_batch
        defect_ids = write_defects_batch(driver, image_id, doc_id, defects)

    # 自动查询 Hazard 整改建议
    remediation_map: dict[str, list] = {}
    if defects:
        from ...services.defect_writer import query_hazard_remediation
        for d in defects:
            dt = d["defect_type"]
            if dt not in remediation_map:
                remediation_map[dt] = query_hazard_remediation(driver, dt, doc_id)

    return {
        "image_id":        image_id,
        "defects":         defects,
        "defect_ids":      defect_ids,
        "remediation_map": remediation_map,
        "total":           len(defects),
    }


@router.get("/defects")
async def list_defects(
    doc_id:      str    = "",
    defect_type: str    = "",
    min_conf:    float  = 0.0,
    limit:       int    = 50,
    driver:      Driver = Depends(get_driver),
):
    """查询已写入图谱的缺陷记录，支持按文档/类型/置信度过滤"""
    with driver.session() as session:
        result = session.run("""
            MATCH (d:Defect)
            WHERE ($doc_id   = '' OR d.doc_id      = $doc_id)
              AND ($dtype    = '' OR d.type         = $dtype)
              AND d.confidence >= $min_conf
            OPTIONAL MATCH (d)-[:DETECTED_IN]->(i:Image)
            RETURN d.defect_id   AS defect_id,
                   d.type        AS type,
                   d.label       AS label,
                   d.confidence  AS confidence,
                   d.description AS description,
                   d.image_id    AS image_id,
                   i.path        AS image_path
            ORDER BY d.confidence DESC
            LIMIT $limit
        """, doc_id=doc_id, dtype=defect_type, min_conf=min_conf, limit=limit)
        defects = [dict(r) for r in result]
    return {"defects": defects, "total": len(defects)}


@router.get("/hazards/{defect_type}")
async def get_hazard_remediation(
    defect_type: str,
    doc_id:      str    = "",
    driver:      Driver = Depends(get_driver),
):
    """查询指定缺陷类型对应的 Hazard 节点和整改建议"""
    from ...services.defect_writer import query_hazard_remediation
    hazards = query_hazard_remediation(driver, defect_type, doc_id)
    return {
        "defect_type": defect_type,
        "hazards":     hazards,
        "total":       len(hazards),
    }
