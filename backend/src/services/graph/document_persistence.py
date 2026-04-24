"""Helpers for persisting documents, sections, and table vectors."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def build_section_payloads(doc_id: str, sections) -> tuple[list[dict], list[dict], list[str]]:
    texts = [f"{section.title}\n{section.content}" for section in sections]
    milvus_data = [
        {
            "chunk_id": section.chunk_id,
            "doc_id": doc_id,
            "text": f"{section.title}\n{section.content}",
            "embedding": None,
        }
        for section in sections
    ]
    sections_data = [
        {
            "chunk_id": section.chunk_id,
            "number": section.number,
            "title": section.title,
            "content": section.content,
            "level": section.level,
            "seq_index": section.seq_index,
            "page_idx": section.page_idx,
            "bbox": section.bbox,
        }
        for section in sections
    ]
    return milvus_data, sections_data, texts


def attach_embeddings(rows: list[dict], embeddings: list) -> list[dict]:
    hydrated = []
    for index, row in enumerate(rows):
        merged = dict(row)
        merged["embedding"] = embeddings[index] if index < len(embeddings) else None
        if merged.get("embedding"):
            hydrated.append(merged)
    return hydrated


def build_parent_pairs(sections) -> list[dict]:
    number_to_chunk = {section.number: section.chunk_id for section in sections}
    pairs = []
    for section in sections:
        parts = section.number.split(".")
        if len(parts) > 1:
            parent_number = ".".join(parts[:-1])
            if parent_number in number_to_chunk:
                pairs.append({"parent_id": number_to_chunk[parent_number], "child_id": section.chunk_id})
    return pairs


def build_next_pairs(sections) -> list[dict]:
    return [
        {"from_id": sections[index].chunk_id, "to_id": sections[index + 1].chunk_id}
        for index in range(len(sections) - 1)
    ]


def build_es_rows(doc_id: str, sections) -> list[dict]:
    return [
        {
            "chunk_id": section.chunk_id,
            "doc_id": doc_id,
            "number": section.number,
            "title": section.title,
            "content": section.content,
        }
        for section in sections
    ]


def write_section_nodes(session, doc_id: str, sections_data: list[dict]) -> None:
    session.run(
        """
        MATCH (d:Document {name: $doc_id})
        UNWIND $sections AS s
        MERGE (sec:Section {chunk_id: s.chunk_id})
        SET sec.doc_id    = $doc_id,
            sec.number    = s.number,
            sec.title     = s.title,
            sec.content   = s.content,
            sec.level     = s.level,
            sec.seq_index = s.seq_index,
            sec.page_idx  = s.page_idx,
            sec.bbox      = s.bbox
        MERGE (d)-[:HAS_SECTION]->(sec)
        """,
        doc_id=doc_id,
        sections=sections_data,
    )


def write_reference_nodes(session, doc_id: str, refs: list[str]) -> None:
    if not refs:
        return
    session.run(
        """
        MATCH (d: Document {name: $doc_id})
        UNWIND $refs AS ref_id
        MERGE (ref: Document {name: ref_id})
        MERGE (d)-[:REFERENCES]->(ref)
        """,
        doc_id=doc_id,
        refs=refs,
    )
    logger.info("写入引用关系 %s -> %s", doc_id, refs)


def write_section_edges(session, parent_pairs: list[dict], next_pairs: list[dict]) -> None:
    if parent_pairs:
        session.run(
            """
            UNWIND $pairs AS p
            MATCH (parent:Section {chunk_id: p.parent_id})
            MATCH (child:Section  {chunk_id: p.child_id})
            MERGE (parent)-[:HAS_SUBSECTION]->(child)
            """,
            pairs=parent_pairs,
        )
        logger.info("写入层级关系 %d 条", len(parent_pairs))
    if next_pairs:
        session.run(
            """
            UNWIND $pairs AS p
            MATCH (a:Section {chunk_id: p.from_id})
            MATCH (b:Section {chunk_id: p.to_id})
            MERGE (a)-[:NEXT_SECTION]->(b)
            """,
            pairs=next_pairs,
        )
        logger.info("写入顺序关系 %d 条", len(next_pairs))


def extract_table_data(doc) -> list[dict]:
    from ..parsing.parser import extract_tables_pdfplumber
    from ..tables.table_extractor import extract_tables_structured

    pdf_path_str = str(doc.pdf_path) if doc.pdf_path else ""
    if not pdf_path_str or not Path(pdf_path_str).exists():
        return []

    sections = [
        {"chunk_id": section.chunk_id, "number": section.number, "page_idx": section.page_idx}
        for section in doc.sections
    ]
    table_data = extract_tables_pdfplumber(Path(pdf_path_str), doc.doc_id, sections)
    if not table_data:
        try:
            table_data = extract_tables_structured(pdf_path_str, doc.doc_id, sections)
        except Exception:
            table_data = []
    return table_data


def write_table_vectors(doc_id: str, table_data: list[dict], embed_texts, upsert_sections) -> None:
    table_texts = [table["markdown"] for table in table_data]
    embeddings = embed_texts(table_texts)
    milvus_rows = [
        {
            "chunk_id": table["table_id"],
            "doc_id": doc_id,
            "text": table["markdown"],
            "embedding": embeddings[index] if index < len(embeddings) else None,
        }
        for index, table in enumerate(table_data)
    ]
    milvus_rows = [row for row in milvus_rows if row.get("embedding")]
    if milvus_rows:
        upsert_sections(milvus_rows)
        logger.info("表格向量写入 Milvus doc_id=%s tables=%d", doc_id, len(milvus_rows))

