from __future__ import annotations

from types import SimpleNamespace

from .reprocess_support import load_sections


def _run_vectorize(driver, doc_id, task, step):
    step("vectorize", "重新生成章节向量...")
    if task.get("cancel_requested", False):
        return -1

    from ..graph.document_persistence import attach_embeddings, build_es_rows, build_section_payloads
    from ..retrieval.embedder import embed_texts
    from ..storage.es_store import index_sections
    from ..storage.milvus_store import delete_section_vectors, upsert_sections

    raw_sections = load_sections(driver, doc_id)
    if not raw_sections:
        return 0

    sections = []
    for seq_index, row in enumerate(raw_sections):
        section = dict(row)
        number = str(section.get("number") or "")
        section.setdefault("level", len([part for part in number.split(".") if part]))
        section.setdefault("seq_index", seq_index)
        sections.append(SimpleNamespace(**section))

    milvus_rows, _, texts = build_section_payloads(doc_id, sections)
    embeddings = embed_texts(texts) if texts else []
    milvus_rows = attach_embeddings(milvus_rows, embeddings)

    if milvus_rows:
        delete_section_vectors(doc_id)
        upsert_sections(milvus_rows)

    with driver.session() as session:
        row = session.run(
            "MATCH (d:Document {name: $doc_id}) RETURN d.title AS title",
            doc_id=doc_id,
        ).single()
        doc_title = row["title"] if row and row["title"] else ""

    es_rows = build_es_rows(doc_id, sections)
    for row in es_rows:
        row["doc_title"] = doc_title
    index_sections(es_rows, embeddings if embeddings else None)
    step("vectorize", f"章节向量重建完成，共 {len(sections)} 个章节")
    return len(sections)
