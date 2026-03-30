from pydantic import BaseModel


class QueryRequest(BaseModel):
    question: str
    strategy: str        = "parallel"
    top_k:    int        = 5
    history:  list[dict] = []
    images:   list[str]  = []   # base64 data URIs, e.g. "data:image/png;base64,..."


class SourceSection(BaseModel):
    chunk_id: str
    doc_id:   str
    number:   str
    title:    str
    score:    float


class QueryResponse(BaseModel):
    answer:  str
    sources: list[SourceSection]