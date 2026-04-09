"""
OCR 增强解析器 — 扫描版 PDF 章节提取

当 pdfplumber 无法提取足够文本时，回退到 PaddleOCR 识别后
再用相同的章节分割正则进行处理。
"""
import re
import logging
from pathlib import Path

from .parser import (
    SECTION_PATTERN,
    clean_content,
    extract_refs,
    extract_meta,
)
from .ocr_engine import render_page_to_image, ocr_page, is_available

logger = logging.getLogger(__name__)


def extract_sections_with_ocr(pdf_path: Path, doc_id: str) -> list[dict]:
    """
    混合策略：
    - 每页先用 pdfplumber 提取文字
    - 若文字过少（扫描页）则 OCR 补充
    - 合并后用章节正则切分
    """
    import pdfplumber

    full_text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            if len(text.strip()) < 30:
                # 扫描页 → OCR
                img = render_page_to_image(str(pdf_path), page_num)
                if img is not None:
                    text = ocr_page(img)
                    logger.info("OCR 处理第 %d 页", page_num + 1)
            full_text += text + "\n"

    # 章节切分（与 parser.py 保持一致）
    matches = list(SECTION_PATTERN.finditer(full_text))
    matches = [m for m in matches if len(m.group(2)) >= 2 and m.group(2) != "_"]

    sections = []
    for i, match in enumerate(matches):
        number = match.group(1)
        title  = match.group(2)
        start  = match.start()
        end    = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
        content = clean_content(full_text[start:end])
        sections.append({
            "chunk_id": f"{doc_id}_{number}",
            "number":   number,
            "title":    title,
            "content":  content,
        })

    return sections


def parse_with_ocr(pdf_path: Path):
    """
    完整解析入口（OCR 增强版），供 parser.parse() 调用。
    返回与 DocumentSchema 相同结构的对象。
    """
    from ..models.schemas import DocumentSchema, SectionSchema

    meta     = extract_meta(pdf_path)
    sections = extract_sections_with_ocr(pdf_path, meta["doc_id"])
    refs     = extract_refs(sections)

    if not meta["doc_id"]:
        raise ValueError(
            f"无法提取文档编号（封面和文件名均无法识别）: {pdf_path.name}"
        )

    return DocumentSchema(
        doc_id         = meta["doc_id"],
        version        = meta["version"],
        title          = meta["title"],
        issue_date     = meta["issue_date"],
        total_sections = len(sections),
        sections       = [SectionSchema(**s) for s in sections],
        refs           = refs,
    )
