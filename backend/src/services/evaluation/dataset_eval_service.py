from __future__ import annotations

import asyncio
import csv
import io
import re
import uuid
import zipfile
from datetime import datetime
from difflib import SequenceMatcher
from typing import Any
from xml.etree import ElementTree as ET

from neo4j import Driver

from ...db.models import User
from ...routers.query.models import QueryRequest
from ...routers.query.sync import query_sync

_tasks: dict[str, dict[str, Any]] = {}

_NS = {
    "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _normalize_text(text: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"[^\w\u4e00-\u9fff]", "", text)
    return text


def _judge_match(expected: str, actual: str) -> tuple[bool, float]:
    exp = _normalize_text(expected)
    ans = _normalize_text(actual)

    if not exp:
        return False, 0.0

    ratio = SequenceMatcher(None, exp, ans).ratio() if ans else 0.0

    if exp in {"对", "错"}:
        if ans.startswith(exp):
            return True, ratio
        if re.search(rf"(^|[^对错]){re.escape(exp)}($|[^对错])", ans):
            return True, ratio
        return False, ratio

    if exp and exp in ans:
        return True, ratio

    if ratio >= 0.72:
        return True, ratio

    if len(exp) >= 12 and len(ans) >= 12:
        overlap = sum(1 for ch in exp if ch in ans)
        if overlap / max(len(exp), 1) >= 0.8:
            return True, ratio

    return False, ratio


def _sheet_rows_from_xlsx(data: bytes) -> list[list[str]]:
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in zf.namelist():
            root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in root.findall("a:si", _NS):
                text = "".join((t.text or "") for t in si.iterfind(".//a:t", _NS))
                shared.append(text)

        wb = ET.fromstring(zf.read("xl/workbook.xml"))
        rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        rel_map = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels}

        sheet_target = None
        for sheet in wb.find("a:sheets", _NS) or []:
            sheet_target = rel_map[sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]]
            break
        if not sheet_target:
            raise ValueError("Excel 文件中未找到工作表")

        sheet_xml = ET.fromstring(zf.read("xl/" + sheet_target))
        sheet_data = sheet_xml.find("a:sheetData", _NS)
        if sheet_data is None:
            return []

        rows: list[list[str]] = []
        for row in sheet_data.findall("a:row", _NS):
            values: list[str] = []
            for cell in row.findall("a:c", _NS):
                cell_type = cell.attrib.get("t")
                value_node = cell.find("a:v", _NS)
                text = ""
                if cell_type == "s" and value_node is not None:
                    text = shared[int(value_node.text or "0")]
                elif cell_type == "inlineStr":
                    inline_node = cell.find("a:is", _NS)
                    if inline_node is not None:
                        text = "".join((t.text or "") for t in inline_node.iterfind(".//a:t", _NS))
                elif value_node is not None:
                    text = value_node.text or ""
                values.append(text.strip())
            if any(values):
                rows.append(values)
        return rows


def _rows_from_upload(filename: str, data: bytes) -> list[dict[str, str]]:
    lower = filename.lower()
    raw_rows: list[list[str]]

    if lower.endswith(".xlsx"):
        raw_rows = _sheet_rows_from_xlsx(data)
    elif lower.endswith(".csv"):
        text = data.decode("utf-8-sig", errors="replace")
        raw_rows = [list(row) for row in csv.reader(io.StringIO(text))]
    else:
        raise ValueError("仅支持 .xlsx 或 .csv 测试集文件")

    if len(raw_rows) < 2:
        raise ValueError("测试集至少需要表头和一行数据")

    headers = [str(h or "").strip() for h in raw_rows[0]]
    question_idx = next((i for i, h in enumerate(headers) if h == "问题"), None)
    answer_idx = next((i for i, h in enumerate(headers) if h == "答案"), None)
    domain_idx = next((i for i, h in enumerate(headers) if h == "专业"), None)

    if question_idx is None or answer_idx is None:
        raise ValueError("表头必须包含“问题”和“答案”列")

    rows: list[dict[str, str]] = []
    for idx, row in enumerate(raw_rows[1:], start=2):
        question = (row[question_idx] if question_idx < len(row) else "").strip()
        expected = (row[answer_idx] if answer_idx < len(row) else "").strip()
        domain = (row[domain_idx] if domain_idx is not None and domain_idx < len(row) else "").strip()
        if not question:
            continue
        rows.append({
            "row_no": str(idx),
            "question": question,
            "expected_answer": expected,
            "domain": domain,
        })

    if not rows:
        raise ValueError("测试集没有可执行的问题行")

    return rows


async def _run_task(
    task_id: str,
    rows: list[dict[str, str]],
    strategy: str,
    top_k: int,
    driver: Driver,
    current_user: User,
) -> None:
    task = _tasks[task_id]
    task["status"] = "running"
    task["started_at"] = _now()

    results: list[dict[str, Any]] = []

    try:
        for idx, row in enumerate(rows, start=1):
            req = QueryRequest(
                question=row["question"],
                strategy=strategy,
                top_k=top_k,
            )
            resp = await query_sync(
                request=None,  # type: ignore[arg-type]
                req=req,
                driver=driver,
                current_user=current_user,
            )

            actual_answer = resp.answer
            matched, similarity = _judge_match(row["expected_answer"], actual_answer)
            source_refs = [f"{s.doc_id} §{s.number}" for s in resp.sources]

            results.append({
                "row_no": int(row["row_no"]),
                "question": row["question"],
                "expected_answer": row["expected_answer"],
                "actual_answer": actual_answer,
                "domain": row["domain"],
                "matched": matched,
                "similarity": round(similarity, 4),
                "source_refs": source_refs,
            })

            task["completed"] = idx
            task["passed"] = sum(1 for item in results if item["matched"])
            task["failed"] = idx - task["passed"]
            task["current_question"] = row["question"][:80]
            task["results_preview"] = results[-20:]

            await asyncio.sleep(0)

        task["status"] = "completed"
        task["finished_at"] = _now()
        task["results"] = results
        task["results_preview"] = results[:50]
        task["summary"] = {
            "total": len(results),
            "passed": task["passed"],
            "failed": task["failed"],
            "pass_rate": round(task["passed"] / max(len(results), 1), 4),
        }
    except Exception as exc:
        task["status"] = "failed"
        task["finished_at"] = _now()
        task["error"] = str(exc)


async def start_dataset_eval(
    filename: str,
    data: bytes,
    strategy: str,
    top_k: int,
    driver: Driver,
    current_user: User,
) -> dict[str, Any]:
    rows = _rows_from_upload(filename, data)
    task_id = uuid.uuid4().hex
    _tasks[task_id] = {
        "task_id": task_id,
        "filename": filename,
        "status": "queued",
        "strategy": strategy,
        "top_k": top_k,
        "created_at": _now(),
        "started_at": None,
        "finished_at": None,
        "total": len(rows),
        "completed": 0,
        "passed": 0,
        "failed": 0,
        "current_question": "",
        "error": "",
        "summary": None,
        "results_preview": [],
        "results": [],
    }
    asyncio.create_task(_run_task(task_id, rows, strategy, top_k, driver, current_user))
    return get_task(task_id)


def get_task(task_id: str) -> dict[str, Any]:
    task = _tasks.get(task_id)
    if not task:
        raise KeyError(task_id)
    return task


def export_task_csv(task_id: str) -> str:
    task = get_task(task_id)
    if task["status"] != "completed":
        raise ValueError("任务尚未完成，暂时不能导出")

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["row_no", "domain", "question", "expected_answer", "actual_answer", "matched", "similarity", "source_refs"])
    for row in task["results"]:
        writer.writerow([
            row["row_no"],
            row["domain"],
            row["question"],
            row["expected_answer"],
            row["actual_answer"],
            "PASS" if row["matched"] else "FAIL",
            row["similarity"],
            " | ".join(row["source_refs"]),
        ])
    return buf.getvalue()
