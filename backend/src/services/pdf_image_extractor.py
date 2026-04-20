"""
src/services/pdf_image_extractor.py
PDF 图片提取服务

从 PDF 中提取图片，为多模态知识图谱做准备：
- 提取每页的图片
- 记录图片在哪一页、哪个章节
- 保存到本地临时路径，同时上传到 MinIO extracted-images 桶
- 返回图片路径和元数据
"""
import logging
import fitz  # pymupdf
from pathlib import Path
from dataclasses import dataclass, field

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
    caption:   str = ""   # 图片说明（从周围文字提取）
    minio_key: str = ""   # MinIO 对象键（上传成功后填充）


def _upload_to_minio(image_data: bytes, image_id: str, ext: str) -> str:
    """
    将图片字节上传到 MinIO extracted-images 桶。
    返回对象键；上传失败返回空字符串（本地文件作为回退）。
    """
    try:
        from ..core.storage import upload_bytes, BUCKET_EXTRACTED_IMAGES
        key = f"{image_id}.{ext}"
        upload_bytes(BUCKET_EXTRACTED_IMAGES, key, image_data, content_type=f"image/{ext}")
        return key
    except Exception as e:
        logger.warning("图片上传 MinIO 失败 image_id=%s: %s", image_id, e)
        return ""


def extract_images_from_pdf(pdf_path: str, doc_id: str) -> list[ExtractedImage]:
    """
    从 PDF 提取所有图片。
    过滤掉太小的图（< 100x100，通常是图标或装饰）。
    每张图片：
      1. 保存到本地 uploads/images/（供后续 VisionService 分析使用）
      2. 异步上传到 MinIO extracted-images 桶（持久化存储）
    """
    doc     = fitz.open(pdf_path)
    results = []

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
                img_path   = IMAGE_DIR / f"{image_id}.{ext}"

                # 保存到本地（供 VLM 分析读取）
                with open(img_path, "wb") as f:
                    f.write(img_bytes)

                # 上传到 MinIO；上传成功后立即删除本地临时文件
                minio_key = _upload_to_minio(img_bytes, image_id, ext)
                if minio_key:
                    try:
                        img_path.unlink(missing_ok=True)
                    except Exception as _ce:
                        logger.warning("删除本地临时图片失败 %s: %s", img_path, _ce)

                caption = _extract_caption(page, img_idx)

                results.append(ExtractedImage(
                    image_id  = image_id,
                    doc_id    = doc_id,
                    page      = page_num + 1,
                    path      = str(img_path) if not minio_key else "",
                    width     = width,
                    height    = height,
                    caption   = caption,
                    minio_key = minio_key,
                ))
                logger.info("提取图片 %s (%dx%d) minio=%s local=%s",
                            image_id, width, height, minio_key or "未上传",
                            "已删除" if minio_key else "保留")

            except Exception as e:
                logger.warning("提取图片失败 page=%d img=%d: %s", page_num + 1, img_idx, e)

    doc.close()
    logger.info("共提取 %d 张图片 doc_id=%s", len(results), doc_id)
    return results


def _extract_caption(page: fitz.Page, img_idx: int) -> str:
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