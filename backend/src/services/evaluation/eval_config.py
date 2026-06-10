"""Evaluation run configuration model."""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class EvalRunConfig(BaseModel):
    dataset_id: str

    # Strategy
    strategy: str = "parallel"         # parallel / graph / multi_hop / agent / es_hybrid
    use_reranker: bool = True
    top_k: int = 5
    source_doc_id: str = ""            # restrict retrieval to one doc (empty = all)

    # LLM overrides (None = use system default)
    llm_model: str | None = None
    llm_temperature: float = 0.1
    llm_max_tokens: int = 512

    # Prompt versions
    prompt_versions: dict[str, str] = Field(default_factory=dict)

    # Execution
    concurrency: int = 3
    timeout_per_question: int = 60
    retry_on_error: int = 1

    # Metadata
    run_name: str = ""
    description: str = ""
    tags: list[str] = Field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()

    @classmethod
    def from_dict(cls, d: dict) -> "EvalRunConfig":
        return cls(**{k: v for k, v in d.items() if k in cls.model_fields})
