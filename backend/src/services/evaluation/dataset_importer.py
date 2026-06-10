"""
Dataset importer — converts xlsx / csv / json / docx → EvalDatasetModel.
Reuses existing objective_doc_eval_parser for xlsx MCQ parsing.
"""
from __future__ import annotations

import csv
import io
import json
import logging
import re
import uuid
from pathlib import Path
from typing import Any

from .dataset_schema import EvalDatasetModel, EvalQuestionModel, ValidationReport

logger = logging.getLogger(__name__)

# Column name aliases
_STEM_COLS   = {"题目", "stem", "question", "问题"}
_ANS_COLS    = {"答案", "answer", "correct_answer", "正确答案"}
_EXP_COLS    = {"解析", "explanation", "解释", "分析"}
_DOC_COLS    = {"来源", "source_doc_id", "source", "文档编号", "规范编号"}
_DIFF_COLS   = {"难度", "difficulty"}
_TAG_COLS    = {"标签", "tags"}
_TYPE_COLS   = {"题型", "question_type", "type"}
_OPT_PATTERN = re.compile(r'^[选项选择]?([A-Ea-e])[:：．\.]?\s*(.+)', re.IGNORECASE)


class DatasetImporter:

    def auto_detect_format(self, path: str) -> str:
        suffix = Path(path).suffix.lower()
        return {".xlsx": "xlsx", ".xls": "xlsx", ".csv": "csv",
                ".json": "json", ".docx": "docx"}.get(suffix, "unknown")

    # ── Public entry points ───────────────────────────────────────────

    def from_bytes(self, data: bytes, filename: str, dataset_name: str = "") -> EvalDatasetModel:
        fmt = self.auto_detect_format(filename)
        if fmt == "xlsx":
            return self._from_xlsx_bytes(data, dataset_name or Path(filename).stem)
        if fmt == "csv":
            return self._from_csv_bytes(data, dataset_name or Path(filename).stem)
        if fmt == "json":
            return self._from_json_bytes(data, dataset_name or Path(filename).stem)
        raise ValueError(f"不支持的格式: {fmt}（支持 xlsx/csv/json）")

    def validate(self, ds: EvalDatasetModel) -> ValidationReport:
        return ValidationReport.from_dataset(ds)

    # ── xlsx ──────────────────────────────────────────────────────────

    def _from_xlsx_bytes(self, data: bytes, name: str) -> EvalDatasetModel:
        try:
            from .objective_doc_eval_parser import extract_objective_questions
            questions_raw = extract_objective_questions(data)
            return self._raw_to_dataset(questions_raw, name)
        except Exception as e:
            logger.warning("openpyxl parser failed (%s), falling back to generic", e)
            return self._xlsx_generic(data, name)

    def _xlsx_generic(self, data: bytes, name: str) -> EvalDatasetModel:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return EvalDatasetModel(name=name)
        header = [str(c or "").strip() for c in rows[0]]
        questions = [self._row_to_question(dict(zip(header, row)), i)
                     for i, row in enumerate(rows[1:]) if any(v for v in row)]
        return self._build_dataset(name, [q for q in questions if q])

    def _raw_to_dataset(self, raw: list[dict], name: str) -> EvalDatasetModel:
        questions = []
        for i, r in enumerate(raw):
            opts = {}
            for label in ("A", "B", "C", "D", "E"):
                v = r.get(f"option_{label}") or r.get(label, "")
                if v:
                    opts[label] = str(v)
            q = EvalQuestionModel(
                id=str(uuid.uuid4()),
                question_type=r.get("question_type", "mcq"),
                stem=str(r.get("stem") or r.get("question", "")),
                options=opts or None,
                correct_answer=str(r.get("answer") or r.get("correct_answer", "")),
                explanation=str(r.get("explanation") or ""),
                source_doc_id=str(r.get("source_doc_id") or ""),
                difficulty=str(r.get("difficulty") or "medium"),
                order_index=i,
            )
            if q.stem:
                questions.append(q)
        return self._build_dataset(name, questions)

    # ── csv ───────────────────────────────────────────────────────────

    def _from_csv_bytes(self, data: bytes, name: str) -> EvalDatasetModel:
        text = data.decode("utf-8-sig", errors="replace")
        reader = csv.DictReader(io.StringIO(text))
        questions = [self._row_to_question(row, i)
                     for i, row in enumerate(reader) if row]
        return self._build_dataset(name, [q for q in questions if q])

    # ── json ──────────────────────────────────────────────────────────

    def _from_json_bytes(self, data: bytes, name: str) -> EvalDatasetModel:
        payload = json.loads(data.decode("utf-8"))
        if isinstance(payload, dict) and "questions" in payload:
            raw = payload["questions"]
            name = payload.get("name", name)
        elif isinstance(payload, list):
            raw = payload
        else:
            raise ValueError("JSON 格式应为 {questions: [...]} 或 [...]")
        questions = [self._row_to_question(r, i) for i, r in enumerate(raw)]
        return self._build_dataset(name, [q for q in questions if q])

    # ── helpers ───────────────────────────────────────────────────────

    def _row_to_question(self, row: dict[str, Any], idx: int) -> EvalQuestionModel | None:
        row_l = {k.lower().strip(): v for k, v in row.items()}

        stem = self._pick(row_l, _STEM_COLS)
        if not stem:
            return None
        answer = self._pick(row_l, _ANS_COLS) or ""
        explanation = self._pick(row_l, _EXP_COLS) or ""
        source = self._pick(row_l, _DOC_COLS) or ""
        difficulty = self._pick(row_l, _DIFF_COLS) or "medium"
        qtype = self._pick(row_l, _TYPE_COLS) or "mcq"

        opts: dict[str, str] = {}
        for k, v in row_l.items():
            m = _OPT_PATTERN.match(k)
            if m and v:
                opts[m.group(1).upper()] = str(v)
        # also try column names like "A", "B", "C", "D"
        for label in ("a", "b", "c", "d", "e"):
            if label in row_l and row_l[label]:
                opts[label.upper()] = str(row_l[label])

        return EvalQuestionModel(
            id=str(uuid.uuid4()),
            question_type=qtype,
            stem=str(stem),
            options=opts or None,
            correct_answer=str(answer),
            explanation=str(explanation),
            source_doc_id=str(source),
            difficulty=str(difficulty),
            order_index=idx,
        )

    @staticmethod
    def _pick(row: dict, keys: set[str]) -> str | None:
        for k in row:
            if k.lower() in keys or any(a in k.lower() for a in keys):
                v = row[k]
                return str(v).strip() if v is not None else None
        return None

    @staticmethod
    def _build_dataset(name: str, questions: list[EvalQuestionModel]) -> EvalDatasetModel:
        ds = EvalDatasetModel(name=name, questions=questions)
        ds.compute_stats()
        return ds


importer = DatasetImporter()
