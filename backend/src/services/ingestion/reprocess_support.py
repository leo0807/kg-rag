from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)
UPLOAD_DIR     = Path("uploads")
DOC_UPLOAD_DIR = Path("uploads") / "docs"


def find_pdf(doc_id: str) -> Path | None:
    """在 uploads/docs/ 和 uploads/ 两个目录中查找文档文件（PDF/DOCX/DOC）。"""
    exts = ["pdf", "PDF", "docx", "DOCX", "doc", "DOC"]
    for base in (DOC_UPLOAD_DIR, UPLOAD_DIR):
        for ext in exts:
            candidates = sorted(base.glob(f"{doc_id}*.{ext}"))
            if candidates:
                return candidates[0]
    return None


def load_sections(driver, doc_id: str) -> list[dict]:
    with driver.session() as session:
        result = session.run("""
            MATCH (d:Document {name: $doc_id})-[:HAS_SECTION]->(s:Section)
            RETURN s.chunk_id AS chunk_id, s.number AS number,
                   s.title AS title, s.content AS content,
                   s.page_idx AS page_idx, s.bbox AS bbox
            ORDER BY s.number
        """, doc_id=doc_id)
        return [dict(r) for r in result]


def load_images(driver, doc_id: str) -> list[dict]:
    with driver.session() as session:
        result = session.run("""
            MATCH (d:Document {name: $doc_id})
            OPTIONAL MATCH (d)-[:HAS_SECTION]->(:Section)-[:HAS_IMAGE]->(section_img:Image)
            WITH d, collect(DISTINCT section_img) AS section_imgs
            OPTIONAL MATCH (d)-[:HAS_IMAGE]->(doc_img:Image)
            WITH section_imgs, collect(DISTINCT doc_img) AS doc_imgs
            WITH section_imgs + doc_imgs AS all_imgs
            UNWIND all_imgs AS img
            WITH DISTINCT img
            WHERE img IS NOT NULL
            RETURN img.image_id AS image_id,
                   img.path AS path,
                   img.minio_path AS minio_path,
                   img.caption AS caption,
                   img.is_drawing AS is_drawing
        """, doc_id=doc_id)
        return [dict(r) for r in result]


def resolve_drawing_image_path(
    image_id: str,
    local_path: Optional[str],
    minio_path: Optional[str],
):
    from ..images.image_file_service import resolve_image_binary_path

    return resolve_image_binary_path(
        image_id=image_id,
        local_path=local_path,
        minio_path=minio_path,
    )


def get_storage_key(driver, doc_id: str) -> str | None:
    """从 Neo4j 读取文档的 MinIO 对象键。"""
    with driver.session() as session:
        row = session.run(
            "MATCH (d:Document {name: $doc_id}) RETURN d.storage_key AS key",
            doc_id=doc_id,
        ).single()
        return row["key"] if row and row["key"] else None


def download_from_minio(doc_id: str, storage_key: str) -> Path | None:
    """从 MinIO 下载文档到 /tmp，返回本地路径。"""
    try:
        from ...core.storage import BUCKET_RAW_DOCUMENTS, download_bytes

        raw_bytes = download_bytes(BUCKET_RAW_DOCUMENTS, storage_key)
        suffix = Path(storage_key).suffix or ".pdf"
        tmp_path = Path(f"/tmp/{doc_id}_reparse{suffix}")
        tmp_path.write_bytes(raw_bytes)
        logger.info("[reparse %s] 从 MinIO 下载到 %s (%d bytes)", doc_id, tmp_path, len(raw_bytes))
        return tmp_path
    except Exception as exc:
        logger.warning("[reparse %s] MinIO 下载失败: %s", doc_id, exc)
        return None


def prepare_reprocess_pdf(doc_id: str, source_path: Path | None, driver) -> tuple[Path | None, list[Path]]:
    """
    为图片/表格抽取准备一个可直接打开的 PDF 路径。
    返回 `(pdf_path, cleanup_paths)`，由调用方在流程结束后统一清理。
    """
    cleanup_paths: list[Path] = []
    path = source_path

    if not path:
        storage_key = get_storage_key(driver, doc_id)
        if storage_key:
            path = download_from_minio(doc_id, storage_key)
            if path:
                cleanup_paths.append(path)
        if not path:
            return None, cleanup_paths

    if path.suffix.lower() in {".doc", ".docx"}:
        from ..parsing.parser import _convert_office_to_pdf

        pdf_path = _convert_office_to_pdf(path)
        if pdf_path != path:
            cleanup_paths.append(pdf_path)
        return pdf_path, cleanup_paths

    return path, cleanup_paths


def cancelled(task: dict) -> bool:
    return task.get("cancel_requested", False)
