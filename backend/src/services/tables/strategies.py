"""Table extraction strategies."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile

from .normalization import MIN_ROWS, df_to_rows, parse_html_table, rows_to_constraints, rows_to_markdown

logger = logging.getLogger(__name__)

CAM_ELOT_AVAILABLE = False
try:
    import camelot as _camelot_check  # noqa: F401

    CAM_ELOT_AVAILABLE = True
except ImportError:
    pass


def _section_chunk_id(sections: list[dict], page_idx: int, total_pages: int, doc_id: str) -> str:
    section_count = len(sections)
    if not section_count:
        return f"{doc_id}_p{page_idx}"
    section_index = min(int(page_idx / max(total_pages, 1) * section_count), section_count - 1)
    return sections[section_index]["chunk_id"]


def is_available() -> bool:
    from ..parsing.ocr_engine import is_struct_available

    return CAM_ELOT_AVAILABLE or is_struct_available()


def extract_tables_structured(pdf_path: str, doc_id: str, sections: list[dict]) -> list[dict]:
    from ..parsing.ocr_engine import ocr_page_struct, render_page_to_image

    try:
        import pdfplumber
    except ImportError:
        logger.warning("pdfplumber 未安装，跳过表格提取")
        return []

    try:
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
    except Exception as exc:
        logger.warning("无法打开 PDF: %s", exc)
        return []

    all_tables: list[dict] = []
    for page_idx in range(total_pages):
        image = render_page_to_image(pdf_path, page_idx)
        if image is None:
            continue
        regions = ocr_page_struct(image)
        table_regions = [region for region in regions if region["type"] == "table"]
        for region_index, region in enumerate(table_regions):
            result = region.get("res", {})
            html = result.get("html") if isinstance(result, dict) else None
            if not html:
                continue
            rows = parse_html_table(html)
            if len(rows) < MIN_ROWS + 1:
                continue
            chunk_id = _section_chunk_id(sections, page_idx, total_pages, doc_id)
            table_id = f"table_{hashlib.md5(f'{doc_id}_{page_idx}_{region_index}'.encode()).hexdigest()[:12]}"
            all_tables.append(
                {
                    "table_id": table_id,
                    "chunk_id": chunk_id,
                    "doc_id": doc_id,
                    "page_index": page_idx,
                    "markdown": rows_to_markdown(rows),
                    "rows_json": json.dumps(rows, ensure_ascii=False),
                    "bbox": region.get("bbox"),
                    "constraints": rows_to_constraints(rows, chunk_id, doc_id, table_id),
                }
            )
    return all_tables


def extract_with_camelot(pdf_path: str, doc_id: str, sections: list[dict]) -> list[dict]:
    if not CAM_ELOT_AVAILABLE:
        return []

    import camelot

    try:
        import pdfplumber

        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
    except Exception:
        total_pages = 1

    all_tables: list[dict] = []
    for page_idx in range(total_pages):
        page_tables = []
        page_str = str(page_idx + 1)
        try:
            lattice_tables = camelot.read_pdf(pdf_path, pages=page_str, flavor="lattice")
            page_tables = [table for table in lattice_tables if table.parsing_report.get("accuracy", 0) >= 50]
        except Exception as exc:
            logger.debug("camelot lattice p%d 失败: %s", page_idx + 1, exc)

        if not page_tables:
            try:
                stream_tables = camelot.read_pdf(pdf_path, pages=page_str, flavor="stream")
                page_tables = [table for table in stream_tables if table.parsing_report.get("accuracy", 0) >= 50]
            except Exception as exc:
                logger.debug("camelot stream p%d 失败: %s", page_idx + 1, exc)

        for table_index, table in enumerate(page_tables):
            rows = df_to_rows(table.df)
            if len(rows) < MIN_ROWS + 1:
                continue
            chunk_id = _section_chunk_id(sections, page_idx, total_pages, doc_id)
            table_id = f"table_{hashlib.md5(f'{doc_id}_{page_idx}_{table_index}_camelot'.encode()).hexdigest()[:12]}"
            all_tables.append(
                {
                    "table_id": table_id,
                    "chunk_id": chunk_id,
                    "doc_id": doc_id,
                    "page_index": page_idx,
                    "markdown": rows_to_markdown(rows),
                    "rows_json": json.dumps(rows, ensure_ascii=False),
                    "bbox": list(table._bbox) if hasattr(table, "_bbox") else None,
                    "constraints": rows_to_constraints(rows, chunk_id, doc_id, table_id),
                    "source": "camelot",
                }
            )
    logger.info("camelot 提取完成 doc_id=%s tables=%d", doc_id, len(all_tables))
    return all_tables


def extract_page_with_vision(pdf_path: str, page_idx: int, doc_id: str, sections: list[dict], total_pages: int) -> list[dict]:
    from PIL import Image as PILImage

    from ..images.vision_service import get_vision_service
    from ..parsing.ocr_engine import render_page_to_image

    image_array = render_page_to_image(pdf_path, page_idx, dpi=150)
    if image_array is None:
        return []

    try:
        image = PILImage.fromarray(image_array)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as handle:
            image_path = handle.name
        image.save(image_path)
    except Exception as exc:
        logger.warning("页面图片保存失败 p%d: %s", page_idx + 1, exc)
        return []

    try:
        result = get_vision_service().analyze_image(image_path, "table")
    except Exception as exc:
        logger.warning("VisionService table p%d 失败: %s", page_idx + 1, exc)
        return []
    finally:
        try:
            os.unlink(image_path)
        except Exception:
            pass

    headers = result.get("headers") or []
    data_rows = result.get("rows") or []
    if not headers and not data_rows:
        return []

    rows = []
    if headers:
        rows.append([str(header) for header in headers])
    for row in data_rows:
        rows.append([str(cell) for cell in row])

    if len(rows) < MIN_ROWS + 1:
        return []

    chunk_id = _section_chunk_id(sections, page_idx, total_pages, doc_id)
    table_id = f"table_{hashlib.md5(f'{doc_id}_{page_idx}_vision'.encode()).hexdigest()[:12]}"
    logger.info("VisionService 提取表格 doc_id=%s p%d rows=%d", doc_id, page_idx + 1, len(rows))
    return [
        {
            "table_id": table_id,
            "chunk_id": chunk_id,
            "doc_id": doc_id,
            "page_index": page_idx,
            "markdown": rows_to_markdown(rows),
            "rows_json": json.dumps(rows, ensure_ascii=False),
            "constraints": rows_to_constraints(rows, chunk_id, doc_id, table_id),
            "source": "vision_service",
        }
    ]


def extract_tables_full(pdf_path: str, doc_id: str, sections: list[dict]) -> list[dict]:
    total_pages = 1
    try:
        import pdfplumber

        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
    except Exception:
        pass

    camelot_tables = extract_with_camelot(pdf_path, doc_id, sections)
    covered_pages = {table["page_index"] for table in camelot_tables}
    vision_tables: list[dict] = []
    for page_idx in range(total_pages):
        if page_idx in covered_pages:
            continue
        vision_tables.extend(extract_page_with_vision(pdf_path, page_idx, doc_id, sections, total_pages))

    all_tables = camelot_tables + vision_tables
    logger.info(
        "表格提取汇总 doc_id=%s camelot=%d vision=%d total=%d",
        doc_id,
        len(camelot_tables),
        len(vision_tables),
        len(all_tables),
    )
    return all_tables


def extract_all_tables(pdf_path: str, doc_id: str, sections: list[dict]) -> list[dict]:
    return [constraint for table in extract_tables_full(pdf_path, doc_id, sections) for constraint in table["constraints"]]

