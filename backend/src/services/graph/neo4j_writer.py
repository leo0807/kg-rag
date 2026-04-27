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
    write_reference_nodes,
    write_section_edges,
    write_section_nodes,
    write_table_vectors,
)
from .versioning import link_version_lineage

logger = logging.getLogger(__name__)

def write_document(doc: DocumentSchema) -> None:
    driver = get_driver()
    milvus_rows, sections_data, texts = build_section_payloads(doc.doc_id, doc.sections)
    embeddings = embed_texts(texts) if texts else []
    milvus_rows = attach_embeddings(milvus_rows, embeddings)
    parent_pairs = build_parent_pairs(doc.sections)
    next_pairs = build_next_pairs(doc.sections)

    with driver.session() as session:
        session.run(
            """
            MERGE (d: Document {name: $doc_id})
            SET d.version = $version,
                d.title   = $title,
                d.issue_date = $issue_date,
                d.doc_type   = 'CPS'
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
        es_rows = build_es_rows(doc.doc_id, doc.sections)
        # 补充 doc_title 字段供 hybrid_search 检索
        for row in es_rows:
            row["doc_title"] = doc.title or ""
        # embeddings 与 sections 等长（build_section_payloads 保证顺序一致）
        index_sections(es_rows, embeddings if embeddings else None)
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
