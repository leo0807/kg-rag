import logging

from ...core.database import get_driver
from ...models.schemas import DocumentSchema
from ..retrieval.embedder import embed_texts
from ..storage.es_store import delete_doc, index_sections
from ..storage.milvus_store import upsert_sections
from .document_persistence import (
    attach_embeddings,
    build_es_rows,
    build_next_pairs,
    build_parent_pairs,
    build_section_payloads,
    extract_table_data,
    fetch_existing_hashes,
    section_content_hash,
    write_reference_nodes,
    write_section_edges,
    write_section_nodes,
    write_table_vectors,
)
from .versioning import link_version_lineage

logger = logging.getLogger(__name__)


def write_formulas(doc_id: str, formulas: list[dict]) -> int:
    """
    将公式列表写入 Neo4j（Formula 节点）并按页码关联到最近章节。
    同时向 Milvus 写入公式向量供语义检索。
    返回成功写入数量。
    """
    if not formulas:
        return 0

    driver = get_driver()
    written = 0

    # 预先查询该文档所有章节的 page_idx，用于归属公式到最近章节
    with driver.session() as session:
        result = session.run(
            """
            MATCH (d:Document {name: $doc_id})-[:HAS_SECTION]->(s:Section)
            WHERE s.page_idx IS NOT NULL
            RETURN s.chunk_id AS chunk_id, s.page_idx AS page_idx
            ORDER BY s.page_idx
            """,
            doc_id=doc_id,
        )
        page_to_chunk: list[tuple[int, str]] = [
            (int(r["page_idx"]), r["chunk_id"]) for r in result
        ]

    def _nearest_chunk(page_num: int) -> str | None:
        if not page_to_chunk:
            return None
        best = min(page_to_chunk, key=lambda x: abs(x[0] - page_num))
        return best[1]

    for f in formulas:
        formula_id = f["formula_id"]
        latex = f["latex"]
        desc = f.get("description", "工程计算公式")
        page_num = f.get("page_num", 0)
        nearest = _nearest_chunk(page_num)

        try:
            with driver.session() as session:
                session.run(
                    """
                    MERGE (fm:Formula {formula_id: $formula_id})
                    SET fm.doc_id       = $doc_id,
                        fm.page_num     = $page_num,
                        fm.latex        = $latex,
                        fm.description  = $desc,
                        fm.rendered_url = ''
                    """,
                    formula_id=formula_id,
                    doc_id=doc_id,
                    page_num=page_num,
                    latex=latex,
                    desc=desc,
                )
                if nearest:
                    session.run(
                        """
                        MATCH (s:Section {chunk_id: $chunk_id})
                        MATCH (fm:Formula {formula_id: $formula_id})
                        MERGE (s)-[:HAS_FORMULA]->(fm)
                        """,
                        chunk_id=nearest,
                        formula_id=formula_id,
                    )
            written += 1
        except Exception as exc:
            logger.warning("Formula 节点写入失败 %s: %s", formula_id, exc)

    # 写入 Milvus 供语义检索
    try:
        from ..retrieval.embedder import embed_texts
        from ..storage.milvus_store import upsert_sections

        milvus_rows = []
        texts = [f"公式：{f.get('description','')} LaTeX: {f['latex']}" for f in formulas]
        embeddings = embed_texts(texts)
        for f, emb in zip(formulas, embeddings):
            milvus_rows.append({
                "chunk_id":  f["formula_id"],
                "doc_id":    doc_id,
                "text":      f"公式：{f.get('description','')} LaTeX: {f['latex']}",
                "embedding": emb,
            })
        if milvus_rows:
            upsert_sections(milvus_rows)
            logger.info("公式向量写入 Milvus doc=%s count=%d", doc_id, len(milvus_rows))
    except Exception as exc:
        logger.warning("公式 Milvus 写入失败（不影响主流程）: %s", exc)

    logger.info("Formula 节点写入完成 doc=%s written=%d", doc_id, written)
    return written


def write_document(doc: DocumentSchema, on_stage=None, driver=None) -> None:
    """on_stage(stage_name, progress_pct) 是可选进度回调，不影响原有调用方。

    Args:
        driver: 显式传入时使用该 driver（Celery task 场景）；
                None 时退回全局 get_driver()（FastAPI 场景）。
    """
    def _notify(stage: str, pct: int):
        if on_stage:
            try:
                on_stage(stage, pct)
            except Exception:
                pass

    if driver is None:
        driver = get_driver()
    milvus_rows, sections_data, texts = build_section_payloads(doc.doc_id, doc.sections)
    embeddings = embed_texts(texts) if texts else []
    _notify("向量化", 35)
    milvus_rows = attach_embeddings(milvus_rows, embeddings)
    parent_pairs = build_parent_pairs(doc.sections)
    next_pairs = build_next_pairs(doc.sections)

    with driver.session() as session:
        session.run(
            """
            MERGE (d: Document {name: $doc_id})
            SET d.version    = $version,
                d.title      = $title,
                d.issue_date = $issue_date,
                d.doc_type   = 'CPS',
                d.created_at = CASE WHEN d.created_at IS NULL THEN datetime() ELSE d.created_at END
            """,
            doc_id=doc.doc_id,
            version=doc.version,
            title=doc.title,
            issue_date=doc.issue_date,
        )

        logger.info("写入 Document 节点 doc_id=%s", doc.doc_id)
        if milvus_rows:
            upsert_sections(milvus_rows)
            logger.info("写入 Milvus 向量 doc_id=%s sections=%d", doc.doc_id, len(milvus_rows))

        write_section_nodes(session, doc.doc_id, sections_data)
        write_reference_nodes(session, doc.doc_id, doc.refs)
        write_section_edges(session, parent_pairs, next_pairs)
        _notify("写入Neo4j", 65)
        es_rows = build_es_rows(doc.doc_id, doc.sections)
        # 补充 doc_title 字段供 hybrid_search 检索
        for row in es_rows:
            row["doc_title"] = doc.title or ""
        # embeddings 与 sections 等长（build_section_payloads 保证顺序一致）
        index_sections(es_rows, embeddings if embeddings else None)
        _notify("ES索引", 90)
        logger.info("写入 ES doc_id=%s sections=%d has_vec=%s",
                    doc.doc_id, len(doc.sections), bool(embeddings))
        link_version_lineage(session, doc.doc_id, doc.version or "")

    try:
        from .entity_writer import write_tables

        table_data = extract_table_data(doc)
        if table_data:
            write_tables(driver, doc.doc_id, table_data)
            try:
                write_table_vectors(doc.doc_id, table_data, embed_texts, upsert_sections)
            except Exception as exc:
                logger.warning("表格 Milvus 写入失败（不影响主流程）: %s", exc)
    except Exception as exc:
        logger.warning("表格提取/写入失败（不影响主流程）: %s", exc)

    logger.info("写入完成 doc_id=%s sections=%d", doc.doc_id, len(doc.sections))


def write_document_incremental(doc: DocumentSchema, driver=None) -> dict:
    """段落级增量更新：只对内容变化的章节重新嵌入和写入。返回变更统计。

    Args:
        driver: 显式传入时使用该 driver（Celery task 场景）；
                None 时退回全局 get_driver()（FastAPI 场景）。
    """
    from ..storage.milvus_store import delete_by_chunk_ids
    from ..storage.es_store import delete_chunks

    if driver is None:
        driver = get_driver()
    new_hashes = {s.chunk_id: section_content_hash(s.number, s.title, s.content) for s in doc.sections}

    with driver.session() as session:
        session.run(
            "MERGE (d:Document {name: $doc_id}) "
            "SET d.version=$version, d.title=$title, d.issue_date=$issue_date, d.doc_type='CPS'",
            doc_id=doc.doc_id, version=doc.version or "", title=doc.title or "", issue_date=doc.issue_date or "",
        )
        existing = fetch_existing_hashes(session, doc.doc_id)

    added   = [s for s in doc.sections if s.chunk_id not in existing]
    updated = [s for s in doc.sections if s.chunk_id in existing and existing[s.chunk_id] != new_hashes[s.chunk_id]]
    skipped = [s for s in doc.sections if s.chunk_id in existing and existing[s.chunk_id] == new_hashes[s.chunk_id]]
    removed_ids = [cid for cid in existing if cid not in new_hashes]

    changed = added + updated
    if changed:
        milvus_rows, sections_data, texts = build_section_payloads(doc.doc_id, changed)
        embeddings = embed_texts(texts) if texts else []
        milvus_rows = attach_embeddings(milvus_rows, embeddings)
        with driver.session() as session:
            write_section_nodes(session, doc.doc_id, sections_data)
        if milvus_rows:
            upsert_sections(milvus_rows)
        es_rows = build_es_rows(doc.doc_id, changed)
        for row in es_rows:
            row["doc_title"] = doc.title or ""
        index_sections(es_rows, embeddings if embeddings else None)

    if changed or removed_ids:
        parent_pairs = build_parent_pairs(doc.sections)
        next_pairs   = build_next_pairs(doc.sections)
        with driver.session() as session:
            if removed_ids:
                session.run(
                    "UNWIND $ids AS cid MATCH (s:Section {chunk_id: cid}) DETACH DELETE s",
                    ids=removed_ids,
                )
            session.run(
                "MATCH (d:Document {name: $doc_id})-[:HAS_SECTION]->(s:Section) "
                "OPTIONAL MATCH (s)-[r:HAS_SUBSECTION|NEXT_SECTION]->() DELETE r",
                doc_id=doc.doc_id,
            )
            write_section_edges(session, parent_pairs, next_pairs)
            write_reference_nodes(session, doc.doc_id, doc.refs)
            link_version_lineage(session, doc.doc_id, doc.version or "")
        if removed_ids:
            delete_by_chunk_ids(removed_ids)
            delete_chunks(removed_ids)

    logger.info(
        "增量更新 doc_id=%s added=%d updated=%d skipped=%d removed=%d",
        doc.doc_id, len(added), len(updated), len(skipped), len(removed_ids),
    )
    return {"added": len(added), "updated": len(updated), "skipped": len(skipped), "removed": len(removed_ids)}


def rewrite_sections(driver, doc) -> int:
    """
    删除文档旧章节并重新写入（用于 reparse 管道）。
    只更新 Neo4j 结构和 ES 索引，不做 embedding（避免 BGE-M3 OOM）。
    返回新写入的章节数。
    """
    doc_id = doc.doc_id
    sections_data = build_section_payloads(doc_id, doc.sections)[1]
    parent_pairs = build_parent_pairs(doc.sections)
    next_pairs = build_next_pairs(doc.sections)

    with driver.session() as session:
        session.run("""
            MATCH (d:Document {name: $doc_id})-[:HAS_SECTION]->(s:Section)
            DETACH DELETE s
        """, doc_id=doc_id)

        session.run("""
            MATCH (d:Document {name: $doc_id})
            SET d.version    = CASE WHEN $version <> ''    THEN $version    ELSE d.version    END,
                d.title      = CASE WHEN $title <> ''      THEN $title      ELSE d.title      END,
                d.issue_date = CASE WHEN $issue_date <> '' THEN $issue_date ELSE d.issue_date END
        """, doc_id=doc_id,
             version=doc.version or "",
             title=doc.title or "",
             issue_date=doc.issue_date or "")

        if not doc.sections:
            return 0

        write_section_nodes(session, doc_id, sections_data)
        write_section_edges(session, parent_pairs, next_pairs)

    try:
        delete_doc(doc_id)
        es_rows = build_es_rows(doc_id, doc.sections)
        for row in es_rows:
            row["doc_title"] = doc.title or ""
        index_sections(es_rows)
    except Exception as exc:
        logger.warning("ES 更新失败（不影响主流程）: %s", exc)

    logger.info("rewrite_sections 完成 doc_id=%s sections=%d", doc_id, len(doc.sections))
    return len(doc.sections)
