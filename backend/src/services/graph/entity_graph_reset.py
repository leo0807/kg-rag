from __future__ import annotations

from neo4j import Driver


def cleanup_stale_document_nodes(driver: Driver, doc_id: str) -> None:
    with driver.session() as session:
        session.run(
            """
            MATCH (n)
            WHERE coalesce(n.doc_id, '') = $doc_id
              AND (n:Tool OR n:Material OR n:Process OR n:Constraint OR n:Table)
              AND NOT (n)--(:Section)
              AND NOT (n)--(:Image)
            DETACH DELETE n
            """,
            doc_id=doc_id,
        )


def reset_document_entity_graph(driver: Driver, doc_id: str) -> None:
    with driver.session() as session:
        session.run(
            """
            MATCH (:Document {name: $doc_id})-[:HAS_SECTION]->(sec:Section)-[r:REQUIRES_TOOL|USES_MATERIAL|INVOLVES_PROCESS]->()
            DELETE r
            """,
            doc_id=doc_id,
        )
    cleanup_stale_document_nodes(driver, doc_id)


def reset_document_text_constraints(driver: Driver, doc_id: str) -> None:
    with driver.session() as session:
        session.run(
            """
            MATCH (c:Constraint)
            WHERE coalesce(c.doc_id, '') = $doc_id
              AND coalesce(c.source, 'text') = 'text'
            DETACH DELETE c
            """,
            doc_id=doc_id,
        )


def reset_document_tables(driver: Driver, doc_id: str) -> None:
    with driver.session() as session:
        session.run(
            """
            MATCH (t:Table)
            WHERE coalesce(t.doc_id, '') = $doc_id
            DETACH DELETE t
            """,
            doc_id=doc_id,
        )
        session.run(
            """
            MATCH (c:Constraint)
            WHERE coalesce(c.doc_id, '') = $doc_id
              AND c.source = 'table'
            DETACH DELETE c
            """,
            doc_id=doc_id,
        )

