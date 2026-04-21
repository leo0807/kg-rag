"""
表格提取 — 多策略提取技术规范表格并映射为 Table 与 Constraint 节点

提取策略（按优先级）：
1. camelot      — 原生 PDF 矢量表格，精度最高（需安装 camelot-py[cv] + ghostscript）
2. VisionService — camelot 未找到表格时，将页面渲染为图片送 VLM 识别（task=table）
3. PP-Structure  — 旧路径，仍保留供直接调用（extract_tables_structured）

功能：
- 将表格解析为统一结构 (list[list[str]])
- 生成 Markdown 表示，保留行列语义
- 将表格行映射为 Constraint 节点，建立 Table -> Constraint 关系
"""
import re
import json
import logging
import hashlib
from html.parser import HTMLParser
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# ── 可选依赖探测 ──────────────────────────────────────────────────────────────
_CAMELOT_AVAILABLE = False
try:
    import camelot as _camelot_check  # noqa: F401
    _CAMELOT_AVAILABLE = True
except ImportError:
    pass

# 列名关键字，用于识别参数/值/单位列
_PARAM_HEADERS  = {"参数", "项目", "名称", "parameter", "item", "要求", "指标"}
_VALUE_HEADERS  = {"值", "数值", "value", "规格", "量值", "要求值", "结果"}
_UNIT_HEADERS   = {"单位", "unit"}
_MIN_ROWS       = 2   # 表格至少含 N 行数据才处理


# ── HTML 表格解析 ──────────────────────────────────────────────────────────────

class _TableHTMLParser(HTMLParser):
    """将 PP-Structure 输出的 HTML 表格解析为 list[list[str]]"""

    def __init__(self):
        super().__init__()
        self.rows: list[list[str]] = []
        self._row:  list[str]      = []
        self._cell: Optional[str]  = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th"):
            self._cell = ""

    def handle_data(self, data):
        if self._cell is not None:
            self._cell += data.strip()

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cell is not None:
            self._row.append(self._cell.strip())
            self._cell = None
        elif tag == "tr" and self._row:
            self.rows.append(self._row)
            self._row = []


def _parse_html_table(html: str) -> list[list[str]]:
    p = _TableHTMLParser()
    p.feed(html)
    return p.rows


def _rows_to_markdown(rows: list[list[str]]) -> str:
    """将 list[list[str]] 转换为 Markdown 表格"""
    if not rows:
        return ""
    
    md_rows = []
    for i, row in enumerate(rows):
        # 处理空单元格并转义 |
        clean_row = [c.replace("|", "\\|") if c else "" for c in row]
        md_rows.append("| " + " | ".join(clean_row) + " |")
        
        # 插入 header 分隔符
        if i == 0:
            md_rows.append("| " + " | ".join(["---"] * len(row)) + " |")
            
    return "\n".join(md_rows)


# ── 约束类型推断与值解析 ────────────────────────────────────────────────────────

_TORQUE_KW  = {"力矩", "扭矩", "torque"}
_TEMP_KW    = {"温度", "temperature", "℃", "°c"}
_TOL_KW     = {"公差", "tolerance", "偏差"}
_SURFACE_KW = {"粗糙度", "roughness", "ra", "rz"}
_PRESSURE_KW = {"压力", "pressure", "mpa", "bar"}

def _infer_constraint_type(param: str) -> str:
    p = param.lower()
    if any(k in p for k in _TORQUE_KW):   return "torque"
    if any(k in p for k in _TEMP_KW):     return "temperature"
    if any(k in p for k in _TOL_KW):      return "tolerance"
    if any(k in p for k in _SURFACE_KW):  return "surface"
    if any(k in p for k in _PRESSURE_KW): return "pressure"
    return "specification"

_RANGE_RE   = re.compile(r'([+-]?[\d.]+)\s*[~～—\-–]\s*([+-]?[\d.]+)')
_SINGLE_RE  = re.compile(r'([+-]?[\d.]+)')
_UNIT_RE    = re.compile(r'([a-zA-Z°℃µμΩ%/]+[\w./°℃]*)')

def _parse_value(raw: str):
    range_m = _RANGE_RE.search(raw)
    if range_m:
        v_min, v_max = range_m.group(1), range_m.group(2)
        rest = raw[range_m.end():]
        unit_m = _UNIT_RE.search(rest)
        return "", v_min, v_max, (unit_m.group(1) if unit_m else "")

    single_m = _SINGLE_RE.search(raw)
    value = single_m.group(1) if single_m else ""
    unit_m = _UNIT_RE.search(raw[single_m.end():] if single_m else raw)
    return value, "", "", (unit_m.group(1) if unit_m else "")


# ── 行 → Constraint 映射 ───────────────────────────────────────────────────────

def _rows_to_constraints(
    rows:     list[list[str]],
    chunk_id: str,
    doc_id:   str,
    table_id: str,
) -> list[dict]:
    if len(rows) < _MIN_ROWS + 1:
        return []

    header = [c.lower() for c in rows[0]]
    data   = rows[1:]

    param_col = next((i for i, h in enumerate(header) if any(k in h for k in _PARAM_HEADERS)), None)
    value_col = next((i for i, h in enumerate(header) if any(k in h for k in _VALUE_HEADERS)), None)
    unit_col  = next((i for i, h in enumerate(header) if any(k in h for k in _UNIT_HEADERS)), None)

    if param_col is None: param_col = 0
    if value_col is None and len(header) > 1: value_col = 1

    constraints = []
    for idx, row in enumerate(data):
        if len(row) <= param_col: continue
        param = row[param_col].strip()
        if not param: continue

        raw_val = row[value_col].strip() if value_col is not None and len(row) > value_col else ""
        raw_unit = row[unit_col].strip() if unit_col is not None and len(row) > unit_col else ""

        value, v_min, v_max, unit = _parse_value(raw_val)
        if raw_unit: unit = raw_unit

        con_type = _infer_constraint_type(param)
        raw_text = f"{param}: {raw_val} {unit}".strip()

        # constraint_id 包含 table_id 和行索引，确保在 Table 下唯一
        cid = hashlib.md5(f"{table_id}_{idx}_{param}".encode()).hexdigest()[:16]

        constraints.append({
            "constraint_id": f"con_{cid}",
            "type":        con_type,
            "value":       value,
            "value_min":   v_min,
            "value_max":   v_max,
            "unit":        unit,
            "description": raw_text,
            "standard":    "",
            "doc_id":      doc_id,
            "chunk_id":    chunk_id,
            "source":      "table",
        })

    return constraints


# ── 主入口 ────────────────────────────────────────────────────────────────────

def is_available() -> bool:
    from .ocr_engine import is_struct_available
    # camelot 可独立提取矢量表格；结构化 OCR 仅作为补充能力。
    return _CAMELOT_AVAILABLE or is_struct_available()


def extract_tables_structured(
    pdf_path: str,
    doc_id:   str,
    sections: list[dict],
) -> list[dict]:
    """
    提取表格并返回结构化数据：
    [{
        "table_id", "chunk_id", "doc_id", "markdown", "rows",
        "constraints": [...]
    }]
    """
    from .ocr_engine import render_page_to_image, ocr_page_struct
    try:
        import pdfplumber
    except ImportError:
        logger.warning("pdfplumber 未安装，跳过表格提取")
        return []

    all_tables: list[dict] = []

    try:
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
    except Exception as e:
        logger.warning("无法打开 PDF: %s", e)
        return []

    n_sec = len(sections)

    for page_idx in range(total_pages):
        img = render_page_to_image(pdf_path, page_idx)
        if img is None: continue

        regions = ocr_page_struct(img)
        table_regions = [r for r in regions if r["type"] == "table"]
        
        for r_idx, region in enumerate(table_regions):
            res = region.get("res", {})
            html = res.get("html") if isinstance(res, dict) else None
            if not html: continue
            
            rows = _parse_html_table(html)
            if len(rows) < _MIN_ROWS + 1: continue

            # 映射到 chunk_id
            sec_idx = min(int(page_idx / max(total_pages, 1) * n_sec), n_sec - 1) if n_sec else 0
            chunk_id = sections[sec_idx]["chunk_id"] if n_sec else f"{doc_id}_p{page_idx}"

            # 生成唯一 table_id
            table_hash = hashlib.md5(f"{doc_id}_{page_idx}_{r_idx}".encode()).hexdigest()[:12]
            table_id = f"table_{table_hash}"

            markdown = _rows_to_markdown(rows)
            constraints = _rows_to_constraints(rows, chunk_id, doc_id, table_id)

            all_tables.append({
                "table_id":    table_id,
                "chunk_id":    chunk_id,
                "doc_id":      doc_id,
                "page_index":  page_idx,
                "markdown":    markdown,
                "rows_json":   json.dumps(rows, ensure_ascii=False),
                "bbox":        region.get("bbox"),
                "constraints": constraints
            })

    return all_tables


# ── camelot 主路径 ─────────────────────────────────────────────────────────────

def _df_to_rows(df) -> list[list[str]]:
    """将 pandas DataFrame 转换为 list[list[str]]，包含表头行。"""
    import pandas as pd
    rows: list[list[str]] = []
    # 将列名作为第一行
    rows.append([str(c) for c in df.columns.tolist()])
    for _, row in df.iterrows():
        rows.append([str(v) if v is not None else "" for v in row.tolist()])
    return rows


def _extract_with_camelot(
    pdf_path: str,
    doc_id:   str,
    sections: list[dict],
) -> list[dict]:
    """
    用 camelot 提取原生 PDF 表格。
    - 先尝试 lattice（有表格线），再尝试 stream（无表格线）
    - 仅保留精度 ≥ 50 的表格
    返回统一表格结构列表。
    """
    if not _CAMELOT_AVAILABLE:
        return []

    import camelot
    n_sec = len(sections)
    all_tables: list[dict] = []

    # 获取总页数
    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as _pdf:
            total_pages = len(_pdf.pages)
    except Exception:
        total_pages = 1

    for page_idx in range(total_pages):
        page_str = str(page_idx + 1)  # camelot 用 1-indexed 字符串
        page_tables = []

        # 第一轮：lattice（有线表格）
        try:
            tlist = camelot.read_pdf(pdf_path, pages=page_str, flavor="lattice")
            page_tables = [t for t in tlist if t.parsing_report.get("accuracy", 0) >= 50]
        except Exception as e:
            logger.debug("camelot lattice p%d 失败: %s", page_idx + 1, e)

        # 第二轮：该页无 lattice 结果时用 stream
        if not page_tables:
            try:
                tlist = camelot.read_pdf(pdf_path, pages=page_str, flavor="stream")
                page_tables = [t for t in tlist if t.parsing_report.get("accuracy", 0) >= 50]
            except Exception as e:
                logger.debug("camelot stream p%d 失败: %s", page_idx + 1, e)

        for t_idx, table in enumerate(page_tables):
            rows = _df_to_rows(table.df)
            if len(rows) < _MIN_ROWS + 1:
                continue

            sec_idx  = min(int(page_idx / max(total_pages, 1) * n_sec), n_sec - 1) if n_sec else 0
            chunk_id = sections[sec_idx]["chunk_id"] if n_sec else f"{doc_id}_p{page_idx}"

            table_hash = hashlib.md5(f"{doc_id}_{page_idx}_{t_idx}_camelot".encode()).hexdigest()[:12]
            table_id   = f"table_{table_hash}"
            markdown   = _rows_to_markdown(rows)
            constraints = _rows_to_constraints(rows, chunk_id, doc_id, table_id)

            all_tables.append({
                "table_id":   table_id,
                "chunk_id":   chunk_id,
                "doc_id":     doc_id,
                "page_index": page_idx,
                "markdown":   markdown,
                "rows_json":  json.dumps(rows, ensure_ascii=False),
                "bbox":       list(table._bbox) if hasattr(table, '_bbox') else None,
                "constraints": constraints,
                "source":     "camelot",
            })

    logger.info("camelot 提取完成 doc_id=%s tables=%d", doc_id, len(all_tables))
    return all_tables


# ── VisionService 降级路径 ─────────────────────────────────────────────────────

def _extract_page_with_vision(
    pdf_path:  str,
    page_idx:  int,
    doc_id:    str,
    sections:  list[dict],
    total_pages: int,
) -> list[dict]:
    """
    对单个页面用 VisionService（task=table）提取表格。
    需要先将页面渲染为图片。
    """
    from .ocr_engine import render_page_to_image
    import tempfile, os
    from PIL import Image as _PILImage

    img_arr = render_page_to_image(pdf_path, page_idx, dpi=150)
    if img_arr is None:
        return []

    # numpy → 临时 PNG 文件（VisionService 需要路径）
    try:
        img_pil = _PILImage.fromarray(img_arr)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name
        img_pil.save(tmp_path)
    except Exception as e:
        logger.warning("页面图片保存失败 p%d: %s", page_idx + 1, e)
        return []

    try:
        from .vision_service import get_vision_service
        result = get_vision_service().analyze_image(tmp_path, "table")
    except Exception as e:
        logger.warning("VisionService table p%d 失败: %s", page_idx + 1, e)
        return []
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

    # 将 VisionService 返回的 {headers, rows} 转换为 list[list[str]]
    headers = result.get("headers") or []
    data_rows = result.get("rows") or []
    if not headers and not data_rows:
        return []

    rows: list[list[str]] = []
    if headers:
        rows.append([str(h) for h in headers])
    for r in data_rows:
        rows.append([str(c) for c in r])

    if len(rows) < _MIN_ROWS + 1:
        return []

    n_sec    = len(sections)
    sec_idx  = min(int(page_idx / max(total_pages, 1) * n_sec), n_sec - 1) if n_sec else 0
    chunk_id = sections[sec_idx]["chunk_id"] if n_sec else f"{doc_id}_p{page_idx}"

    table_hash  = hashlib.md5(f"{doc_id}_{page_idx}_vision".encode()).hexdigest()[:12]
    table_id    = f"table_{table_hash}"
    markdown    = _rows_to_markdown(rows)
    constraints = _rows_to_constraints(rows, chunk_id, doc_id, table_id)

    logger.info("VisionService 提取表格 doc_id=%s p%d rows=%d", doc_id, page_idx + 1, len(rows))
    return [{
        "table_id":    table_id,
        "chunk_id":    chunk_id,
        "doc_id":      doc_id,
        "page_index":  page_idx,
        "markdown":    markdown,
        "rows_json":   json.dumps(rows, ensure_ascii=False),
        "constraints": constraints,
        "source":      "vision_service",
    }]


# ── 主入口（重写）────────────────────────────────────────────────────────────

def extract_all_tables(pdf_path: str, doc_id: str, sections: list[dict]) -> list[dict]:
    """
    多策略表格提取，按优先级降级：
      1. camelot（原生 PDF 矢量表格，精度最高）
      2. VisionService task=table（camelot 未找到表格的页面）

    返回打散后的 Constraint 列表（与旧接口保持兼容）。
    如需完整表格数据请调用 extract_tables_full()。
    """
    all_tables = extract_tables_full(pdf_path, doc_id, sections)
    return [con for t in all_tables for con in t["constraints"]]


def extract_tables_full(
    pdf_path: str,
    doc_id:   str,
    sections: list[dict],
) -> list[dict]:
    """
    多策略表格提取，返回完整表格对象列表（含 markdown、rows_json、constraints）。

    策略：
      1. camelot 提取全部页面
      2. 对 camelot 未找到表格的页面，用 VisionService 补充
    """
    # 获取总页数
    total_pages = 1
    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as _pdf:
            total_pages = len(_pdf.pages)
    except Exception:
        pass

    # ── 第一步：camelot ──────────────────────────────────────────────────────
    camelot_tables = _extract_with_camelot(pdf_path, doc_id, sections)
    pages_covered  = {t["page_index"] for t in camelot_tables}

    # ── 第二步：VisionService 补充没有表格的页面 ─────────────────────────────
    vision_tables: list[dict] = []
    pages_needing_vision = [p for p in range(total_pages) if p not in pages_covered]

    if pages_needing_vision:
        logger.info(
            "camelot 未覆盖 %d 页，尝试 VisionService: doc_id=%s",
            len(pages_needing_vision), doc_id,
        )
        for page_idx in pages_needing_vision:
            vt = _extract_page_with_vision(pdf_path, page_idx, doc_id, sections, total_pages)
            vision_tables.extend(vt)

    all_tables = camelot_tables + vision_tables
    logger.info(
        "表格提取汇总 doc_id=%s camelot=%d vision=%d total=%d",
        doc_id, len(camelot_tables), len(vision_tables), len(all_tables),
    )
    return all_tables
