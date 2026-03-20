from pydantic import BaseModel

class SectionSchema(BaseModel):
    chunk_id: str
    number: str
    title: str
    content: str

class DocumentSchema(BaseModel):
    doc_id:     str
    version:    str
    title:      str
    issue_date: str
    total_sections: int
    sections:   list[SectionSchema]
    refs:       list[str] = []

