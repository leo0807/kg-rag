import logging
from ..core.database import get_driver
from ..models.schemas import DocumentSchema
from .embedder import embed_texts

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
        texts = [f"{s.title}\n{s.content}" for s in doc.sections]
        embeddings = embed_texts(texts)

        sections_data = [
            {
                "chunk_id":  s.chunk_id,
                "number":    s.number,
                "title":     s.title,
                "content":   s.content,
                "embedding": embeddings[i],
            }
            for i, s in enumerate(doc.sections)
        ]

        session.run("""
            MATCH (d:Document {name: $doc_id})
            UNWIND $sections AS s
            MERGE (sec:Section {chunk_id: s.chunk_id})
            SET sec.doc_id    = $doc_id,
                sec.number    = s.number,
                sec.title     = s.title,
                sec.content   = s.content,
                sec.embedding = s.embedding
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

        # 第四条请求：写入章节层级关系（HAS_SUBSECTION）和顺序关系（NEXT_SECTION）
        number_to_chunk = {s.number: s.chunk_id for s in doc.sections}

        parent_pairs = []
        for s in doc.sections:
            parts = s.number.split(".")
            if len(parts) > 1:
                parent_number = ".".join(parts[:-1])
                if parent_number in number_to_chunk:
                    parent_pairs.append({
                        "parent_id": number_to_chunk[parent_number],
                        "child_id":  s.chunk_id,
                    })

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

        next_pairs = [
            {"from_id": doc.sections[i].chunk_id, "to_id": doc.sections[i + 1].chunk_id}
            for i in range(len(doc.sections) - 1)
        ]
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

    logger.info("写入完成 doc_id=%s sections=%d", doc.doc_id, len(doc.sections))
