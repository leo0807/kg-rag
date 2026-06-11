"""
I2: DB models for local model management.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from .base import Base

try:
    from sqlalchemy.dialects.postgresql import JSONB as JSON
except ImportError:
    from sqlalchemy import JSON


def _uuid() -> str:
    return str(uuid.uuid4())


class LocalModel(Base):
    """Registry of locally deployed AI models."""
    __tablename__ = "local_models"

    id:          Mapped[str]  = mapped_column(String(36), primary_key=True, default=_uuid)
    name:        Mapped[str]  = mapped_column(String(200), nullable=False, index=True)
    version:     Mapped[str]  = mapped_column(String(50),  default="latest")
    backend:     Mapped[str]  = mapped_column(String(50),  nullable=False)  # ollama/vllm/llamacpp/tgi
    model_path:  Mapped[str]  = mapped_column(String(500), default="")
    description: Mapped[str]  = mapped_column(String(500), default="")

    # Specs
    parameters_b:           Mapped[float | None] = mapped_column(Float, nullable=True)
    quantization:           Mapped[str]          = mapped_column(String(20), default="fp16")
    context_length:         Mapped[int | None]   = mapped_column(Integer,   nullable=True)
    gpu_memory_required_gb: Mapped[float | None] = mapped_column(Float, nullable=True)
    cpu_memory_required_gb: Mapped[float | None] = mapped_column(Float, nullable=True)

    # State
    is_loaded:   Mapped[bool]        = mapped_column(Boolean, default=False)
    load_time:   Mapped[float | None] = mapped_column(Float, nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Use-case tags e.g. ["qa", "embedding", "vision", "reranker"]
    use_cases: Mapped[Any] = mapped_column(JSON, default=list)

    # Performance metrics (updated after benchmark)
    benchmark_metrics: Mapped[Any] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class FinetuneJob(Base):
    """I8.2: Fine-tuning job registry."""
    __tablename__ = "finetune_jobs"

    id:           Mapped[str]  = mapped_column(String(36),  primary_key=True, default=_uuid)
    name:         Mapped[str]  = mapped_column(String(200), nullable=False)
    base_model:   Mapped[str]  = mapped_column(String(200), nullable=False)
    dataset_path: Mapped[str]  = mapped_column(String(500), default="")

    # Training hyper-params
    method:        Mapped[str]        = mapped_column(String(50),  default="lora")
    learning_rate: Mapped[float]      = mapped_column(Float,       default=2e-4)
    epochs:        Mapped[int]        = mapped_column(Integer,     default=3)
    batch_size:    Mapped[int]        = mapped_column(Integer,     default=4)

    # Status
    status:        Mapped[str]       = mapped_column(String(50),  default="pending")
    progress:      Mapped[int]       = mapped_column(Integer,     default=0)
    current_step:  Mapped[int]       = mapped_column(Integer,     default=0)
    total_steps:   Mapped[int]       = mapped_column(Integer,     default=0)

    # Metrics
    train_loss: Mapped[float | None] = mapped_column(Float, nullable=True)
    eval_loss:  Mapped[float | None] = mapped_column(Float, nullable=True)
    metrics:    Mapped[Any]          = mapped_column(JSON,  default=dict)

    output_path: Mapped[str]         = mapped_column(String(500), default="")

    started_at:   Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at:   Mapped[datetime]        = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
