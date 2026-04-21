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


class QueryResponse(BaseModel):
    answer:  str
    sources: list[SourceSection]