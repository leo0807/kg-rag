from pathlib import Path
from pydantic import BaseModel
from typing import Optional, List

class SectionSchema(BaseModel):
    chunk_id: str
    number: str
    title: str
    content: str
    level: int = 1          # 章节深度：1=一级，2=二级，3=三级，4=四级
    seq_index: int = 0      # 文档内顺序下标（0-based），用于排序；不替代 number
    page_idx: Optional[int] = None
    bbox: Optional[List[float]] = None  # [x0, top, x1, bottom]

class DocumentSchema(BaseModel):
    doc_id:     str
    version:    str
    title:      str
    issue_date: str
    total_sections: int
    sections:   list[SectionSchema]
    refs:       list[str] = []
    pdf_path:   Optional[Path] = None  # 转换后的 PDF 路径（用于表格提取）

