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
    # table row fields
    content_type: str = "section"
    table_id:  str | None = None
    row_index: int | None = None
    headers:   list[str] = []
    row_data:  dict | None = None


class QueryMetrics(BaseModel):
    total_ms:               int = 0
    stages:                 dict[str, int] = {}   # stage_name -> ms
    tokens:                 dict[str, int] = {}   # prompt/completion/total
    cost_usd:               float = 0.0
    candidates_retrieved:   int = 0
    candidates_after_rerank:int = 0


class QueryResponse(BaseModel):
    type:           str = "answer"
    answer:         str
    sources:        list[SourceSection]
    expansion_info: list[str] = []
    metrics:        QueryMetrics | None = None
    iterations:     int | None = None
    message:        str | None = None
    options:        list[str] = []
    original_question: str | None = None
