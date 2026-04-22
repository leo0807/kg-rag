from __future__ import annotations

from pydantic import BaseModel


class QueryRequest(BaseModel):
    question:   str
    strategy:   str        = "parallel"
    top_k:      int        = 5
    history:    list[dict] = []
    images:     list[str]  = []   # base64 data URIs, e.g. "data:image/png;base64,..."
    use_hyde:   bool       = False
    hyde_alpha: float      = 0.5  # 假设答案向量权重（0=纯原始问题，1=纯假设答案）


class SourceSection(BaseModel):
    chunk_id: str
    doc_id:   str
    number:   str
    title:    str
    score:    float
    page_idx: int | None = None
    bbox: list[float] | None = None
    source_type: list[str] = []
    retrieval_trace: list[str] = []
    is_graph_expanded: bool = False
    is_vector_hit: bool = False
    is_fulltext_hit: bool = False
    is_gnn_hit: bool = False


class QueryResponse(BaseModel):
    answer:  str
    sources: list[SourceSection]
