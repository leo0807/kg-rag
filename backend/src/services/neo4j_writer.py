import logging
from ..core.database import get_driver
from ..models.schemas import DocumentSchema

logger = logging.getLogger(__name__)

def write_document(doc: DocumentSchema) -> None:
    # 把解析好的文档写入 Neo4j
    driver = get_driver()

    with driver.session() as session:
        # 第一条请求：写入 Document 节点
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
        # 第二条请求：批量写入所有 Section 节点并建立关系
        sections_data = [
            {
                "chunk_id": s.chunk_id,
                "number":   s.number,
                "title":    s.title,
                "content":  s.content,
            }
            for s in doc.sections
        ]

        session.run("""
            MATCH (d:Document {name: $doc_id})
            UNWIND $sections AS s
            MERGE (sec:Section {chunk_id: s.chunk_id})
            SET sec.doc_id  = $doc_id,
                sec.number  = s.number,
                sec.title   = s.title,
                sec.content = s.content
            MERGE (d)-[:HAS_SECTION]->(sec)
        """,
        doc_id=doc.doc_id,
        sections=sections_data,
        )

        # 第三条请求：写入引用关系
        if doc.refs:
            session.run(
                """
                MATCH (d: Document {name: $doc_id})
                UNWIND $refs AS ref_id
                MERGE (ref: Document {name: ref_id})
                MERGE (d)-[:REFERENCES]->(ref)
                """,
                doc_id=doc.doc_id,
                refs=doc.refs,
            )
            logger.info("写入引用关系 %s -> %s", doc.doc_id, doc.refs)

    logger.info("写入完成 doc_id=%s sections=%d", doc.doc_id, len(doc.sections))
