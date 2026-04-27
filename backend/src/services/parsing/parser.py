"""
公开 API：parse(file_path) → DocumentSchema

内部实现已拆分到各子模块：
  parser_patterns  — 正则常量
  parser_heading   — 标题检测与 bbox 工具
  parser_toc       — 目录过滤与后处理
  parser_meta      — 元数据提取（标题、编号、日期）
  parser_sections  — 章节切分
  parser_tables    — 表格提取
  parser_office    — Office 文件转换
"""
from __future__ import annotations

import logging
from pathlib import Path

from ...models.schemas import DocumentSchema, SectionSchema
from .parser_meta import extract_meta, extract_refs, clean_content
from .parser_sections import extract_sections
from .parser_office import _convert_office_to_pdf, _extract_doc_id_from_filename, _find_soffice

# Re-export symbols that other modules import directly from parser
from .parser_patterns import SECTION_PATTERNS, SECTION_PATTERN  # noqa: F401
from .parser_heading import (  # noqa: F401
    fix_token_spacing,
    is_likely_section_title,
    _match_section_heading,
)
from .parser_tables import extract_tables_pdfplumber  # noqa: F401

logger = logging.getLogger(__name__)


def parse(file_path: "Path | str") -> DocumentSchema:
    """解析文档，按扩展名路由到对应解析器。"""
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix in (".doc", ".docx"):
        pdf_path = _convert_office_to_pdf(path)
        doc = _parse_pdf(pdf_path, fallback_doc_id=_extract_doc_id_from_filename(path))
        doc.pdf_path = pdf_path
        return doc

    return _parse_pdf(path)


def _parse_pdf(pdf_path: Path, fallback_doc_id: str = "") -> DocumentSchema:
    """从 PDF 文件提取元数据、章节和引用。"""
    try:
        from .ocr_engine import is_available as ocr_available, pdf_has_scanned_pages
        if ocr_available() and pdf_has_scanned_pages(str(pdf_path)):
            from .ocr_parser import parse_with_ocr
            return parse_with_ocr(pdf_path)
    except Exception as e:
        logger.warning("OCR 路由失败，降级到标准解析: %s", e)

    meta = extract_meta(pdf_path)
    if not meta["doc_id"]:
        if fallback_doc_id:
            meta["doc_id"] = fallback_doc_id
        else:
            raise ValueError(
                f"无法提取文档编号（封面和文件名均无法识别）: {pdf_path.name}"
            )

    sections = extract_sections(pdf_path, meta["doc_id"])
    refs = extract_refs(sections)

    return DocumentSchema(
        doc_id=meta["doc_id"],
        version=meta["version"],
        title=meta["title"],
        issue_date=meta["issue_date"],
        total_sections=len(sections),
        sections=[SectionSchema(**s) for s in sections],
        refs=refs,
        pdf_path=pdf_path,
    )
