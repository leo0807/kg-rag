"""Pydantic schemas for the E-module evaluation dataset system."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class EvalQuestionModel(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    question_type: str = "mcq"   # mcq / multi_select / true_false / fill_blank / open
    stem: str
    options: dict[str, str] | None = None   # {"A": "text", "B": "text", ...}
    correct_answer: str                      # "A" / "AB" / "对" / free text
    explanation: str = ""
    source_doc_id: str = ""
    source_section: str = ""
    difficulty: str = "medium"              # easy / medium / hard
    tags: list[str] = Field(default_factory=list)
    order_index: int = 0

    model_config = {"from_attributes": True}


class EvalDatasetModel(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    version: str = "1.0"
    description: str = ""
    source_doc_ids: list[str] = Field(default_factory=list)
    questions: list[EvalQuestionModel] = Field(default_factory=list)
    total_count: int = 0
    type_distribution: dict[str, int] = Field(default_factory=dict)
    difficulty_distribution: dict[str, int] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    def compute_stats(self) -> None:
        self.total_count = len(self.questions)
        type_dist: dict[str, int] = {}
        diff_dist: dict[str, int] = {}
        for q in self.questions:
            type_dist[q.question_type] = type_dist.get(q.question_type, 0) + 1
            diff_dist[q.difficulty]    = diff_dist.get(q.difficulty, 0) + 1
        self.type_distribution       = type_dist
        self.difficulty_distribution = diff_dist


class ValidationError(BaseModel):
    question_index: int
    field: str
    message: str


class ValidationReport(BaseModel):
    valid: bool
    total: int
    errors: list[ValidationError] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @classmethod
    def from_dataset(cls, ds: EvalDatasetModel) -> "ValidationReport":
        errors: list[ValidationError] = []
        warnings: list[str] = []

        for i, q in enumerate(ds.questions):
            if not q.stem.strip():
                errors.append(ValidationError(question_index=i, field="stem", message="题目不能为空"))
            if not q.correct_answer.strip():
                errors.append(ValidationError(question_index=i, field="correct_answer", message="答案不能为空"))
            if q.question_type in ("mcq", "multi_select") and not q.options:
                warnings.append(f"第{i+1}题：选择题缺少选项")
            if q.question_type == "mcq" and q.options:
                if q.correct_answer.upper() not in [k.upper() for k in q.options]:
                    errors.append(ValidationError(
                        question_index=i, field="correct_answer",
                        message=f"答案 '{q.correct_answer}' 不在选项 {list(q.options.keys())} 中"
                    ))

        if not ds.name.strip():
            errors.append(ValidationError(question_index=-1, field="name", message="数据集名称不能为空"))
        if ds.total_count == 0:
            warnings.append("数据集没有题目")

        return cls(valid=len(errors) == 0, total=len(ds.questions), errors=errors, warnings=warnings)
