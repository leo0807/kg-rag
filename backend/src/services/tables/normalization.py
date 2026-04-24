"""Table normalization helpers."""

from __future__ import annotations

import hashlib
import re
from html.parser import HTMLParser
from typing import Optional

PARAM_HEADERS = {"参数", "项目", "名称", "parameter", "item", "要求", "指标"}
VALUE_HEADERS = {"值", "数值", "value", "规格", "量值", "要求值", "结果"}
UNIT_HEADERS = {"单位", "unit"}
MIN_ROWS = 2

TORQUE_KW = {"力矩", "扭矩", "torque"}
TEMP_KW = {"温度", "temperature", "℃", "°c"}
TOL_KW = {"公差", "tolerance", "偏差"}
SURFACE_KW = {"粗糙度", "roughness", "ra", "rz"}
PRESSURE_KW = {"压力", "pressure", "mpa", "bar"}

RANGE_RE = re.compile(r"([+-]?[\d.]+)\s*[~～—\\-–]\s*([+-]?[\d.]+)")
SINGLE_RE = re.compile(r"([+-]?[\d.]+)")
UNIT_RE = re.compile(r"([a-zA-Z°℃µμΩ%/]+[\w./°℃]*)")


class TableHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows: list[list[str]] = []
        self._row: list[str] = []
        self._cell: Optional[str] = None

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


def parse_html_table(html: str) -> list[list[str]]:
    parser = TableHTMLParser()
    parser.feed(html)
    return parser.rows


def rows_to_markdown(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    md_rows = []
    for index, row in enumerate(rows):
        clean_row = [cell.replace("|", "\\|") if cell else "" for cell in row]
        md_rows.append("| " + " | ".join(clean_row) + " |")
        if index == 0:
            md_rows.append("| " + " | ".join(["---"] * len(row)) + " |")
    return "\n".join(md_rows)


def infer_constraint_type(param: str) -> str:
    lower = param.lower()
    if any(keyword in lower for keyword in TORQUE_KW):
        return "torque"
    if any(keyword in lower for keyword in TEMP_KW):
        return "temperature"
    if any(keyword in lower for keyword in TOL_KW):
        return "tolerance"
    if any(keyword in lower for keyword in SURFACE_KW):
        return "surface"
    if any(keyword in lower for keyword in PRESSURE_KW):
        return "pressure"
    return "specification"


def parse_value(raw: str):
    range_match = RANGE_RE.search(raw)
    if range_match:
        value_min, value_max = range_match.group(1), range_match.group(2)
        rest = raw[range_match.end() :]
        unit_match = UNIT_RE.search(rest)
        return "", value_min, value_max, (unit_match.group(1) if unit_match else "")

    single_match = SINGLE_RE.search(raw)
    value = single_match.group(1) if single_match else ""
    unit_match = UNIT_RE.search(raw[single_match.end() :] if single_match else raw)
    return value, "", "", (unit_match.group(1) if unit_match else "")


def rows_to_constraints(rows: list[list[str]], chunk_id: str, doc_id: str, table_id: str) -> list[dict]:
    if len(rows) < MIN_ROWS + 1:
        return []

    header = [cell.lower() for cell in rows[0]]
    data = rows[1:]
    param_col = next((i for i, value in enumerate(header) if any(k in value for k in PARAM_HEADERS)), None)
    value_col = next((i for i, value in enumerate(header) if any(k in value for k in VALUE_HEADERS)), None)
    unit_col = next((i for i, value in enumerate(header) if any(k in value for k in UNIT_HEADERS)), None)

    if param_col is None:
        param_col = 0
    if value_col is None and len(header) > 1:
        value_col = 1

    constraints = []
    for index, row in enumerate(data):
        if len(row) <= param_col:
            continue
        param = row[param_col].strip()
        if not param:
            continue

        raw_value = row[value_col].strip() if value_col is not None and len(row) > value_col else ""
        raw_unit = row[unit_col].strip() if unit_col is not None and len(row) > unit_col else ""
        value, value_min, value_max, unit = parse_value(raw_value)
        if raw_unit:
            unit = raw_unit

        constraint_id = hashlib.md5(f"{table_id}_{index}_{param}".encode()).hexdigest()[:16]
        constraints.append(
            {
                "constraint_id": f"con_{constraint_id}",
                "type": infer_constraint_type(param),
                "value": value,
                "value_min": value_min,
                "value_max": value_max,
                "unit": unit,
                "description": f"{param}: {raw_value} {unit}".strip(),
                "standard": "",
                "doc_id": doc_id,
                "chunk_id": chunk_id,
                "source": "table",
            }
        )
    return constraints


def df_to_rows(df) -> list[list[str]]:
    rows = [[str(column) for column in df.columns.tolist()]]
    for _, row in df.iterrows():
        rows.append([str(value) if value is not None else "" for value in row.tolist()])
    return rows

