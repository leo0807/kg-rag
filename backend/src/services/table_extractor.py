"""
表格提取 — 基于 PP-Structure 提取技术规范表格并映射为 Constraint 节点

依赖: ocr_engine（PP-Structure）+ pdfplumber（页面→section 映射）
"""
import re
import json
import logging
from html.parser import HTMLParser
from typing import Optional

logger = logging.getLogger(__name__)

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


# ── 约束类型推断 ───────────────────────────────────────────────────────────────

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


# ── 值解析（范围 / 单点）─────────────────────────────────────────────────────

_RANGE_RE   = re.compile(r'([+-]?[\d.]+)\s*[~～—\-–]\s*([+-]?[\d.]+)')
_SINGLE_RE  = re.compile(r'([+-]?[\d.]+)')
_UNIT_RE    = re.compile(r'([a-zA-Z°℃µμΩ%/]+[\w./°℃]*)')


def _parse_value(raw: str):
    """返回 (value, value_min, value_max, unit)"""
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
) -> list[dict]:
    """
    将表格行列表映射为 write_constraints() 所需的 constraint dict 列表。
    自动识别参数列 / 值列 / 单位列。
    """
    if len(rows) < _MIN_ROWS + 1:   # header + data
        return []

    header = [c.lower() for c in rows[0]]
    data   = rows[1:]

    # 列索引检测
    param_col = next((i for i, h in enumerate(header) if any(k in h for k in _PARAM_HEADERS)), None)
    value_col = next((i for i, h in enumerate(header) if any(k in h for k in _VALUE_HEADERS)), None)
    unit_col  = next((i for i, h in enumerate(header) if any(k in h for k in _UNIT_HEADERS)), None)

    # 若未检测到参数列，尝试用第 0 列
    if param_col is None:
        param_col = 0
    if value_col is None and len(header) > 1:
        value_col = 1

    constraints = []
    for row in data:
        if len(row) <= param_col:
            continue
        param = row[param_col].strip()
        if not param:
            continue

        raw_val = row[value_col].strip() if value_col is not None and len(row) > value_col else ""
        raw_unit = row[unit_col].strip() if unit_col is not None and len(row) > unit_col else ""

        value, v_min, v_max, unit = _parse_value(raw_val)
        if raw_unit:
            unit = raw_unit

        con_type = _infer_constraint_type(param)
        raw_text = f"{param}: {raw_val} {unit}".strip()

        constraints.append({
            "constraint_id": f"{chunk_id}_{param[:20]}".replace(" ", "_"),
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
    from .ocr_engine import is_available as ocr_avail
    return ocr_avail()


def extract_all_tables(
    pdf_path: str,
    doc_id:   str,
    sections: list[dict],
) -> list[dict]:
    """
    遍历 PDF 每页，用 PP-Structure 提取表格，转换为 Constraint 列表。

    sections: [{"chunk_id": ..., "number": ..., ...}]
    """
    from .ocr_engine import render_page_to_image, ocr_page_struct
    try:
        import pdfplumber
    except ImportError:
        logger.warning("pdfplumber 未安装，跳过表格提取")
        return []

    all_constraints: list[dict] = []

    try:
        with pdfplumber.open(pdf_path) as pdf:
            total = len(pdf.pages)
    except Exception as e:
        logger.warning("无法打开 PDF: %s", e)
        return []

    # 页号 → chunk_id（按比例分段映射）
    n_sec = len(sections)

    for page_idx in range(total):
        img = render_page_to_image(pdf_path, page_idx)
        if img is None:
            continue

        regions = ocr_page_struct(img)
        table_regions = [r for r in regions if r["type"] == "table"]
        if not table_regions:
            continue

        # 按比例将当前页映射到最近章节
        sec_idx   = min(int(page_idx / max(total, 1) * n_sec), n_sec - 1) if n_sec else 0
        chunk_id  = sections[sec_idx]["chunk_id"] if n_sec else f"{doc_id}_p{page_idx}"

        for region in table_regions:
            res = region.get("res", {})
            html = res.get("html") if isinstance(res, dict) else None
            if not html:
                continue
            rows = _parse_html_table(html)
            cons = _rows_to_constraints(rows, chunk_id, doc_id)
            all_constraints.extend(cons)
            logger.info("页%d 表格提取 %d 条约束 chunk=%s", page_idx + 1, len(cons), chunk_id)

    return all_constraints
