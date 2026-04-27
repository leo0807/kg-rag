from __future__ import annotations

"""PDF 图片提取服务（公共入口）"""
import logging
import re
from pathlib import Path
from typing import Any

from .image_utils import ExtractedImage, compute_image_content_hash, register_image_hash, persist_image_bytes
from .docx_image_extractor import extract_images_from_docx

try:
    import fitz  # pymupdf
except ImportError:
    fitz = None

logger = logging.getLogger(__name__)


def _page_image_xrefs(page: Any) -> list[int]:
    return [int(item[0]) for item in page.get_images(full=True)]


def _should_fallback_to_page_snapshots(doc: Any, sample_pages: int = 6) -> bool:
    sampled_counts: list[int] = []
    unique_xrefs: set[int] = set()
    total_refs = 0
    for page_idx in range(min(len(doc), sample_pages)):
        refs = _page_image_xrefs(doc[page_idx])
        if not refs:
            continue
        sampled_counts.append(len(refs))
        unique_xrefs.update(refs)
        total_refs += len(refs)
    if len(sampled_counts) < 2:
        return False
    min_count = min(sampled_counts)
    max_count = max(sampled_counts)
    repeated_ratio = (len(unique_xrefs) / total_refs) if total_refs else 1.0
    return min_count >= 20 and max_count - min_count <= 2 and repeated_ratio <= 0.35


def _extract_page_caption(page: Any, page_num: int) -> str:
    blocks = page.get_text("blocks")
    for block in blocks:
        text = re.sub(r"\s+", " ", (block[4] or "").strip())
        if 4 <= len(text) <= 120:
            return text
    return f"第{page_num}页"


def _extract_caption(page: Any, img_idx: int) -> str:
    blocks = page.get_text("blocks")
    for block in blocks:
        text = block[4].strip()
        if text.startswith("图") and len(text) < 100:
            return text
    return ""


def _extract_page_snapshots(doc: Any, doc_id: str, dpi: int = 110) -> list[ExtractedImage]:
    results: list[ExtractedImage] = []
    matrix = fitz.Matrix(dpi / 72, dpi / 72)
    for page_num in range(len(doc)):
        page = doc[page_num]
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        image_bytes = pix.tobytes("jpeg")
        image_id = f"{doc_id}_page{page_num + 1}_snapshot"
        content_hash = compute_image_content_hash(image_bytes)
        path, minio_key = persist_image_bytes(image_id=image_id, ext="jpeg", image_bytes=image_bytes)
        results.append(ExtractedImage(
            image_id=image_id, doc_id=doc_id, page=page_num + 1,
            path=path, width=pix.width, height=pix.height,
            content_hash=content_hash, caption=_extract_page_caption(page, page_num + 1),
            minio_key=minio_key,
        ))
    logger.info("整页快照抽取完成 doc_id=%s pages=%d", doc_id, len(results))
    return results


def extract_images_from_pdf(pdf_path: str, doc_id: str) -> list[ExtractedImage]:
    if fitz is None:
        logger.warning("pymupdf 未安装，跳过图片提取 doc_id=%s", doc_id)
        return []
    doc = fitz.open(pdf_path)
    if _should_fallback_to_page_snapshots(doc):
        logger.info("检测到共享嵌入资源型 PDF，切换整页快照抽取 doc_id=%s", doc_id)
        try:
            return _extract_page_snapshots(doc, doc_id)
        finally:
            doc.close()

    results: list[ExtractedImage] = []
    seen_hashes: set[str] = set()
    duplicate_count = 0

    for page_num in range(len(doc)):
        page = doc[page_num]
        for img_idx, img in enumerate(page.get_images(full=True)):
            xref = img[0]
            try:
                base_image = doc.extract_image(xref)
                width  = base_image["width"]
                height = base_image["height"]
                if width < 100 or height < 100:
                    continue
                image_id = f"{doc_id}_page{page_num + 1}_img{img_idx}"
                ext       = base_image["ext"]
                img_bytes = base_image["image"]
                content_hash, is_duplicate = register_image_hash(seen_hashes, img_bytes)
                if is_duplicate:
                    duplicate_count += 1
                    logger.info("跳过重复图片 doc_id=%s page=%d img=%d hash=%s",
                                doc_id, page_num + 1, img_idx, content_hash[:12])
                    continue
                path, minio_key = persist_image_bytes(image_id=image_id, ext=ext, image_bytes=img_bytes)
                results.append(ExtractedImage(
                    image_id=image_id, doc_id=doc_id, page=page_num + 1,
                    path=path, width=width, height=height,
                    content_hash=content_hash, caption=_extract_caption(page, img_idx),
                    minio_key=minio_key,
                ))
                logger.info("提取图片 %s (%dx%d) minio=%s local=%s",
                            image_id, width, height, minio_key or "未上传",
                            "已删除" if minio_key else "保留")
            except Exception as e:
                logger.warning("提取图片失败 page=%d img=%d: %s", page_num + 1, img_idx, e)

    doc.close()
    logger.info("共提取 %d 张图片 doc_id=%s 去重跳过=%d", len(results), doc_id, duplicate_count)
    return results


def extract_images_from_document(
    source_path: str,
    doc_id: str,
    sections: list[dict] | None = None,
) -> list[ExtractedImage]:
    suffix = Path(source_path).suffix.lower()
    if suffix == ".docx":
        results = extract_images_from_docx(source_path, doc_id, sections)
        if results:
            return results
    return extract_images_from_pdf(source_path, doc_id)
