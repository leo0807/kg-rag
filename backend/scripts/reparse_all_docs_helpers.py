from __future__ import annotations

from pathlib import Path


def neo4j_rewrite_sections(driver, doc_id: str, sections: list) -> int:
    if not sections:
        return 0
    sections_data = [
        {
            "chunk_id": s["chunk_id"],
            "number": s["number"],
            "title": s["title"],
            "content": s["content"],
            "level": s["level"],
            "seq_index": s["seq_index"],
            "page_idx": s.get("page_idx"),
            "bbox": s.get("bbox"),
        }
        for s in sections
    ]
    with driver.session() as session:
        session.run(
            "MATCH (d:Document {name:$d})-[:HAS_SECTION]->(s:Section) DETACH DELETE s",
            d=doc_id,
        )
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
        n2c = {s["number"]: s["chunk_id"] for s in sections}
        parent_pairs = []
        for s in sections:
            parts = s["number"].split(".")
            if len(parts) > 1:
                parent_num = ".".join(parts[:-1])
                if parent_num in n2c:
                    parent_pairs.append(
                        {"parent_id": n2c[parent_num], "child_id": s["chunk_id"]}
                    )
        if parent_pairs:
            session.run(
                "UNWIND $p AS p "
                "MATCH (a:Section{chunk_id:p.parent_id}) "
                "MATCH (b:Section{chunk_id:p.child_id}) "
                "MERGE (a)-[:HAS_SUBSECTION]->(b)",
                p=parent_pairs,
            )
        next_pairs = [
            {"from_id": sections[i]["chunk_id"], "to_id": sections[i + 1]["chunk_id"]}
            for i in range(len(sections) - 1)
        ]
        if next_pairs:
            session.run(
                "UNWIND $p AS p "
                "MATCH (a:Section{chunk_id:p.from_id}) "
                "MATCH (b:Section{chunk_id:p.to_id}) "
                "MERGE (a)-[:NEXT_SECTION]->(b)",
                p=next_pairs,
            )
    return len(sections)


def parse_doc(storage_key: str, doc_id: str) -> list[dict]:
    from src.core.storage import download_bytes, BUCKET_RAW_DOCUMENTS
    from src.services.parsing.parser import parse

    suffix = Path(storage_key).suffix.lower()
    tmp_path = Path(f"/tmp/{doc_id}_reparse{suffix}")
    try:
        raw = download_bytes(BUCKET_RAW_DOCUMENTS, storage_key)
        tmp_path.write_bytes(raw)

        doc_schema = parse(tmp_path)

        if hasattr(doc_schema, "sections"):
            return [
                {
                    "chunk_id": s.chunk_id,
                    "number": s.number,
                    "title": s.title,
                    "content": s.content,
                    "level": s.level,
                    "seq_index": s.seq_index,
                    "page_idx": getattr(s, "page_idx", None),
                    "bbox": getattr(s, "bbox", None),
                }
                for s in doc_schema.sections
            ]
        secs = doc_schema.get("sections", []) if isinstance(doc_schema, dict) else []
        if secs and hasattr(secs[0], "chunk_id"):
            return [
                {
                    "chunk_id": s.chunk_id,
                    "number": s.number,
                    "title": s.title,
                    "content": s.content,
                    "level": s.level,
                    "seq_index": s.seq_index,
                    "page_idx": getattr(s, "page_idx", None),
                    "bbox": getattr(s, "bbox", None),
                }
                for s in secs
            ]
        return secs
    finally:
        tmp_path.unlink(missing_ok=True)
