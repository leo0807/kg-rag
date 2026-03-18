import logging
from ..core.database import get_driver
from ..models.schemas import DocumentSchema

logger = logging.getLogger(__name__)

def write_document(doc: DocumentSchema) -> None:
    # 把解析好的文档写入 Neo4j
    driver = get_driver()

    with driver.session() as session:
        # 写入 Document 节点
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
        # 写入 Section 节点并建立关系
        for section in doc.sections:
            session.run(
                """
                MERGE (s: Section {chunk_id: $chunk_id})
                SET s.doc_id  = $doc_id,
                    s.number  = $number,
                    s.title   = $title,
                    s.content = $content
                """,
            chunk_id=section.chunk_id,
            doc_id=doc.doc_id,
            number=section.number,
            title=section.title,
            content=section.content,
            )

            session.run("""
                MATCH (d:Document {name: $doc_id})
                MATCH (s:Section  {chunk_id: $chunk_id})
                MERGE (d)-[:HAS_SECTION]->(s)
            """,
            doc_id=doc.doc_id,
            chunk_id=section.chunk_id,
            )

        logger.info("写入 %d 个 Section 节点", len(doc.sections))
