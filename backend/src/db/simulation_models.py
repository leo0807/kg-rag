"""K1.1: SQLAlchemy ORM models for simulation cases, parameters, results, rules, workflows."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from .base import Base

try:
    from sqlalchemy.dialects.postgresql import JSONB as JSON, ARRAY
    from sqlalchemy import String as _S
    _ArrayStr = lambda: ARRAY(_S)
except ImportError:
    from sqlalchemy import JSON
    _ArrayStr = lambda: JSON


def _uuid() -> str:
    return str(uuid.uuid4())


class SimulationCase(Base):
    __tablename__ = "simulation_cases"

    id:          Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id:   Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)

    case_name:   Mapped[str] = mapped_column(String(200), nullable=False)
    case_code:   Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True, index=True)
    description: Mapped[str] = mapped_column(Text, default="")

    domain:      Mapped[str] = mapped_column(String(50), default="structural", index=True)
    application: Mapped[str] = mapped_column(String(100), default="", index=True)

    related_specs:    Mapped[Any] = mapped_column(JSON, default=list)
    related_sections: Mapped[Any] = mapped_column(JSON, default=list)

    software:         Mapped[str] = mapped_column(String(50), default="")
    software_version: Mapped[str] = mapped_column(String(50), default="")

    inputs:       Mapped[Any] = mapped_column(JSON, default=dict)
    outputs:      Mapped[Any] = mapped_column(JSON, default=dict)
    input_files:  Mapped[Any] = mapped_column(JSON, default=list)
    result_files: Mapped[Any] = mapped_column(JSON, default=list)
    images:       Mapped[Any] = mapped_column(JSON, default=list)

    author_id:        Mapped[str | None] = mapped_column(String(36), nullable=True)
    project_code:     Mapped[str] = mapped_column(String(100), default="")
    confidence_level: Mapped[str] = mapped_column(String(20), default="初步")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class SimulationParameter(Base):
    __tablename__ = "simulation_parameters"

    id:             Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    case_id:        Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    parameter_name: Mapped[str] = mapped_column(String(100), nullable=False)
    parameter_type: Mapped[str] = mapped_column(String(50), default="boundary")

    value:          Mapped[Any] = mapped_column(JSON, default=dict)
    unit:           Mapped[str] = mapped_column(String(50), default="")

    numeric_value:  Mapped[float | None] = mapped_column(Float, nullable=True)
    min_value:      Mapped[float | None] = mapped_column(Float, nullable=True)
    max_value:      Mapped[float | None] = mapped_column(Float, nullable=True)

    notes:          Mapped[str] = mapped_column(Text, default="")


class SimulationResult(Base):
    __tablename__ = "simulation_results"

    id:          Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    case_id:     Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    result_type: Mapped[str] = mapped_column(String(50), default="stress")
    result_name: Mapped[str] = mapped_column(String(100), nullable=False)

    max_value:   Mapped[float | None] = mapped_column(Float, nullable=True)
    min_value:   Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_value:   Mapped[float | None] = mapped_column(Float, nullable=True)
    unit:        Mapped[str] = mapped_column(String(50), default="")

    detail_data:        Mapped[Any] = mapped_column(JSON, default=dict)
    distribution:       Mapped[Any] = mapped_column(JSON, default=dict)
    critical_locations: Mapped[Any] = mapped_column(JSON, default=list)

    pass_criteria: Mapped[str] = mapped_column(Text, default="")
    pass_status:   Mapped[str] = mapped_column(String(20), default="unknown")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SimulationRule(Base):
    __tablename__ = "simulation_rules"

    id:        Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    rule_type: Mapped[str] = mapped_column(String(50), default="design")

    title:          Mapped[str] = mapped_column(String(500), nullable=False)
    condition:      Mapped[str] = mapped_column(Text, default="")
    recommendation: Mapped[str] = mapped_column(Text, default="")
    confidence:     Mapped[float] = mapped_column(Float, default=0.5)

    source_cases:  Mapped[Any] = mapped_column(JSON, default=list)
    extracted_at:  Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    verified_by:  Mapped[str | None] = mapped_column(String(36), nullable=True)
    verified_at:  Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    applied_count: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SimulationWorkflow(Base):
    __tablename__ = "simulation_workflows"

    id:          Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id:   Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    name:        Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")

    template_case_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    parameter_space:  Mapped[Any] = mapped_column(JSON, default=dict)

    doe_type:     Mapped[str] = mapped_column(String(50), default="latin_hypercube")
    sample_count: Mapped[int] = mapped_column(Integer, default=10)

    status:         Mapped[str] = mapped_column(String(50), default="draft")
    total_runs:     Mapped[int] = mapped_column(Integer, default=0)
    completed_runs: Mapped[int] = mapped_column(Integer, default=0)

    submit_target:  Mapped[str] = mapped_column(String(50), default="local")
    cluster_config: Mapped[Any] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
