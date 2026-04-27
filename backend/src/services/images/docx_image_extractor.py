from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from .image_utils import ExtractedImage, register_image_hash, persist_image_bytes

logger = logging.getLogger(__name__)


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


def extract_images_from_docx(
    docx_path: str,
    doc_id: str,
    sections: list[dict] | None = None,
) -> list[ExtractedImage]:
    """直接从 DOCX 的内嵌媒体提取图片。"""
    try:
        from docx import Document as DocxDocument
        from docx.oxml.ns import qn
    except ImportError:
        logger.warning("python-docx 未安装，DOCX 图片提取降级 doc_id=%s", doc_id)
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
            path, minio_key = persist_image_bytes(image_id=image_id, ext=ext, image_bytes=img_bytes)
            page = max(int((current_section or {}).get("page_idx", -1)) + 1, 1)
            chunk_id = str((current_section or {}).get("chunk_id") or "")
            results.append(ExtractedImage(
                image_id=image_id, doc_id=doc_id, page=page,
                path=path, width=0, height=0,
                content_hash=content_hash, caption=caption,
                minio_key=minio_key, chunk_id=chunk_id,
            ))

    logger.info("DOCX 图片提取完成 doc_id=%s count=%d", doc_id, len(results))
    return results
