from __future__ import annotations

"""
src/services/pdf_image_extractor.py
PDF 图片提取服务

从 PDF 中提取图片，为多模态知识图谱做准备：
- 提取每页的图片
- 记录图片在哪一页、哪个章节
- 保存到本地临时路径，同时上传到 MinIO extracted-images 桶
- 返回图片路径和元数据
"""
import hashlib
import logging
import re
from pathlib import Path
from dataclasses import dataclass
from typing import Any

try:
    import fitz  # pymupdf
except ImportError:  # pragma: no cover - 运行环境缺依赖时走降级
    fitz = None

logger = logging.getLogger(__name__)

IMAGE_DIR = Path("uploads/images")
IMAGE_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class ExtractedImage:
    image_id:  str        # 唯一ID，格式：{doc_id}_page{page}_img{idx}
    doc_id:    str
    page:      int
    path:      str        # 本地文件路径（处理期间保留，处理完毕后可清理）
    width:     int
    height:    int
    content_hash: str     # 图片内容哈希，用于文档内去重
    caption:   str = ""   # 图片说明（从周围文字提取）
    minio_key: str = ""   # MinIO 对象键（上传成功后填充）
    chunk_id:  str = ""   # 所属章节（若能识别）


def compute_image_content_hash(image_bytes: bytes) -> str:
    """基于图片二进制计算稳定哈希，用于检测重复抽取。"""
    return hashlib.sha256(image_bytes).hexdigest()


def register_image_hash(seen_hashes: set[str], image_bytes: bytes) -> tuple[str, bool]:
    """注册图片哈希并返回 `(hash, 是否重复)`。"""
    content_hash = compute_image_content_hash(image_bytes)
    if content_hash in seen_hashes:
        return content_hash, True
    seen_hashes.add(content_hash)
    return content_hash, False


def _upload_to_minio(image_data: bytes, image_id: str, ext: str) -> str:
    """
    将图片字节上传到 MinIO extracted-images 桶。
    返回对象键；上传失败返回空字符串（本地文件作为回退）。
    """
    try:
        from ...core.storage import upload_bytes, BUCKET_EXTRACTED_IMAGES
        key = f"{image_id}.{ext}"
        upload_bytes(BUCKET_EXTRACTED_IMAGES, key, image_data, content_type=f"image/{ext}")
        return key
    except Exception as e:
        logger.warning("图片上传 MinIO 失败 image_id=%s: %s", image_id, e)
        return ""


def _persist_image_bytes(
    *,
    image_id: str,
    ext: str,
    image_bytes: bytes,
) -> tuple[str, str]:
    """
    将图片保存到本地并尽量上传 MinIO。
    返回 `(local_path, minio_key)`。
    """
    img_path = IMAGE_DIR / f"{image_id}.{ext}"
    with open(img_path, "wb") as f:
        f.write(image_bytes)

    minio_key = _upload_to_minio(image_bytes, image_id, ext)
    if minio_key:
        try:
            img_path.unlink(missing_ok=True)
        except Exception as exc:
            logger.warning("删除本地临时图片失败 %s: %s", img_path, exc)
    return (str(img_path) if not minio_key else "", minio_key)


def _page_image_xrefs(page: Any) -> list[int]:
    return [int(item[0]) for item in page.get_images(full=True)]


def _section_maps(sections: list[dict] | None) -> tuple[dict[str, dict], dict[str, dict]]:
    by_number: dict[str, dict] = {}
    by_title: dict[str, dict] = {}
    for section in sections or []:
        number = str(section.get("number") or "").strip()
        title = re.sub(r"\s+", " ", str(section.get("title") or "").strip())
        if number:
            by_number[number] = section
        if title:
            by_title[title] = section
    return by_number, by_title


def _match_docx_section(text: str, sections: list[dict] | None) -> dict | None:
    if not text or not sections:
        return None

    from ..parsing.parser import _match_section_heading, is_likely_section_title

    by_number, by_title = _section_maps(sections)
    heading = _match_section_heading(text)
    if heading and is_likely_section_title(heading[0], heading[1]):
        section = by_number.get(heading[0])
        if section:
            return section
        title = re.sub(r"\s+", " ", heading[1].strip())
        return by_title.get(title)
    return by_title.get(re.sub(r"\s+", " ", text.strip()))


def _extract_images_from_docx(
    docx_path: str,
    doc_id: str,
    sections: list[dict] | None = None,
) -> list[ExtractedImage]:
    """
    直接从 DOCX 的内嵌媒体提取图片，避免 DOCX→PDF 后共享资源重复的问题。
    """
    try:
        from docx import Document as DocxDocument
        from docx.oxml.ns import qn
    except ImportError:
        logger.warning("python-docx 未安装，DOCX 图片提取降级为 PDF 路径 doc_id=%s", doc_id)
        return []

    doc = DocxDocument(docx_path)
    seen_hashes: set[str] = set()
    results: list[ExtractedImage] = []
    current_section: dict | None = None
    seq = 0

    for para in doc.paragraphs:
        text = re.sub(r"\s+", " ", para.text.strip())
        matched_section = _match_docx_section(text, sections)
        if matched_section:
            current_section = matched_section

        caption = text if text.startswith("图") and len(text) < 120 else ""
        for blip in para._p.xpath(".//a:blip"):
            rel_id = blip.get(qn("r:embed"))
            if not rel_id:
                continue
            image_part = doc.part.related_parts.get(rel_id)
            if image_part is None:
                continue

            img_bytes = image_part.blob
            content_hash, is_duplicate = register_image_hash(seen_hashes, img_bytes)
            if is_duplicate:
                continue

            ext = Path(str(getattr(image_part, "partname", "image.png"))).suffix.lstrip(".") or "png"
            seq += 1
            image_id = f"{doc_id}_img_{seq}"
            path, minio_key = _persist_image_bytes(
                image_id=image_id,
                ext=ext,
                image_bytes=img_bytes,
            )
            page = max(int((current_section or {}).get("page_idx", -1)) + 1, 1)
            chunk_id = str((current_section or {}).get("chunk_id") or "")
            results.append(ExtractedImage(
                image_id=image_id,
                doc_id=doc_id,
                page=page,
                path=path,
                width=0,
                height=0,
                content_hash=content_hash,
                caption=caption,
                minio_key=minio_key,
                chunk_id=chunk_id,
            ))

    logger.info("DOCX 图片提取完成 doc_id=%s count=%d", doc_id, len(results))
    return results


def _should_fallback_to_page_snapshots(doc: Any, sample_pages: int = 6) -> bool:
    """
    识别 Office 文档转 PDF 后的“共享资源重复挂到每页”场景。
    这类 PDF 用 raw image extraction 会把整本文档压成第一页的一批图片。
    """
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


def _extract_page_snapshots(doc: Any, doc_id: str, dpi: int = 110) -> list[ExtractedImage]:
    """
    对可疑 PDF 走整页快照抽取，避免共享嵌入资源导致的重复图片/错误页码。
    每页最多生成一张图片，保留真实页码。
    """
    results: list[ExtractedImage] = []
    matrix = fitz.Matrix(dpi / 72, dpi / 72)

    for page_num in range(len(doc)):
        page = doc[page_num]
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        image_bytes = pix.tobytes("jpeg")
        image_id = f"{doc_id}_page{page_num + 1}_snapshot"
        content_hash = compute_image_content_hash(image_bytes)
        path, minio_key = _persist_image_bytes(
            image_id=image_id,
            ext="jpeg",
            image_bytes=image_bytes,
        )
        results.append(ExtractedImage(
            image_id=image_id,
            doc_id=doc_id,
            page=page_num + 1,
            path=path,
            width=pix.width,
            height=pix.height,
            content_hash=content_hash,
            caption=_extract_page_caption(page, page_num + 1),
            minio_key=minio_key,
        ))
    logger.info("整页快照抽取完成 doc_id=%s pages=%d", doc_id, len(results))
    return results


def extract_images_from_pdf(pdf_path: str, doc_id: str) -> list[ExtractedImage]:
    """
    从 PDF 提取所有图片。
    过滤掉太小的图（< 100x100，通常是图标或装饰）。
    每张图片：
      1. 保存到本地 uploads/images/（供后续 VisionService 分析使用）
      2. 异步上传到 MinIO extracted-images 桶（持久化存储）
    """
    if fitz is None:
        logger.warning("pymupdf 未安装，跳过图片提取 doc_id=%s", doc_id)
        return []

    doc     = fitz.open(pdf_path)
    if _should_fallback_to_page_snapshots(doc):
        logger.info("检测到共享嵌入资源型 PDF，切换整页快照抽取 doc_id=%s", doc_id)
        try:
            return _extract_page_snapshots(doc, doc_id)
        finally:
            doc.close()

    results = []
    seen_hashes: set[str] = set()
    duplicate_count = 0

    for page_num in range(len(doc)):
        page       = doc[page_num]
        image_list = page.get_images(full=True)

        for img_idx, img in enumerate(image_list):
            xref = img[0]
            try:
                base_image = doc.extract_image(xref)
                width      = base_image["width"]
                height     = base_image["height"]

                # 过滤太小的图
                if width < 100 or height < 100:
                    continue

                image_id   = f"{doc_id}_page{page_num + 1}_img{img_idx}"
                ext        = base_image["ext"]
                img_bytes  = base_image["image"]
                content_hash, is_duplicate = register_image_hash(seen_hashes, img_bytes)
                if is_duplicate:
                    duplicate_count += 1
                    logger.info(
                        "跳过重复图片 doc_id=%s page=%d img=%d hash=%s",
                        doc_id,
                        page_num + 1,
                        img_idx,
                        content_hash[:12],
                    )
                    continue

                path, minio_key = _persist_image_bytes(
                    image_id=image_id,
                    ext=ext,
                    image_bytes=img_bytes,
                )

                caption = _extract_caption(page, img_idx)

                results.append(ExtractedImage(
                    image_id  = image_id,
                    doc_id    = doc_id,
                    page      = page_num + 1,
                    path      = path,
                    width     = width,
                    height    = height,
                    content_hash = content_hash,
                    caption   = caption,
                    minio_key = minio_key,
                ))
                logger.info("提取图片 %s (%dx%d) minio=%s local=%s",
                            image_id, width, height, minio_key or "未上传",
                            "已删除" if minio_key else "保留")

            except Exception as e:
                logger.warning("提取图片失败 page=%d img=%d: %s", page_num + 1, img_idx, e)

    doc.close()
    logger.info(
        "共提取 %d 张图片 doc_id=%s 去重跳过=%d",
        len(results),
        doc_id,
        duplicate_count,
    )
    return results


def extract_images_from_document(
    source_path: str,
    doc_id: str,
    sections: list[dict] | None = None,
) -> list[ExtractedImage]:
    suffix = Path(source_path).suffix.lower()
    if suffix == ".docx":
        results = _extract_images_from_docx(source_path, doc_id, sections)
        if results:
            return results
    return extract_images_from_pdf(source_path, doc_id)


def _extract_caption(page: Any, img_idx: int) -> str:
    """
    从页面文字中提取图片说明
    查找包含"图"字的文字块作为 caption
    """
    blocks = page.get_text("blocks")
    for block in blocks:
        text = block[4].strip()
        if text.startswith("图") and len(text) < 100:
            return text
    return ""
