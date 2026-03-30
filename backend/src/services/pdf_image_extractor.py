"""
src/services/pdf_image_extractor.py
PDF 图片提取服务

从 PDF 中提取图片，为多模态知识图谱做准备：
- 提取每页的图片
- 记录图片在哪一页、哪个章节
- 保存到本地，返回图片路径和元数据
"""
import logging
import fitz  # pymupdf
from pathlib import Path
from dataclasses import dataclass

logger = logging.getLogger(__name__)

IMAGE_DIR = Path("uploads/images")
IMAGE_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class ExtractedImage:
    image_id:   str   # 唯一ID，格式：{doc_id}_page{page}_img{idx}
    doc_id:     str
    page:       int
    path:       str   # 本地文件路径
    width:      int
    height:     int
    caption:    str = ""  # 图片说明（从周围文字提取）


def extract_images_from_pdf(pdf_path: str, doc_id: str) -> list[ExtractedImage]:
    """
    从 PDF 提取所有图片
    过滤掉太小的图（< 100x100，通常是图标或装饰）
    """
    doc     = fitz.open(pdf_path)
    results = []

    for page_num in range(len(doc)):
        page        = doc[page_num]
        image_list  = page.get_images(full=True)

        for img_idx, img in enumerate(image_list):
            xref = img[0]
            try:
                base_image = doc.extract_image(xref)
                width      = base_image["width"]
                height     = base_image["height"]

                # 过滤太小的图
                if width < 100 or height < 100:
                    continue

                image_id  = f"{doc_id}_page{page_num + 1}_img{img_idx}"
                ext       = base_image["ext"]
                img_path  = IMAGE_DIR / f"{image_id}.{ext}"

                with open(img_path, "wb") as f:
                    f.write(base_image["image"])

                # 提取图片周围的文字作为 caption
                caption = _extract_caption(page, img_idx)

                results.append(ExtractedImage(
                    image_id = image_id,
                    doc_id   = doc_id,
                    page     = page_num + 1,
                    path     = str(img_path),
                    width    = width,
                    height   = height,
                    caption  = caption,
                ))
                logger.info("提取图片 %s (%dx%d)", image_id, width, height)

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