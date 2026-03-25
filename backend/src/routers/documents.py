import logging
from fastapi import APIRouter, Depends
from neo4j import Driver
from ..core.database import get_driver

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["documents"])

@router.get("/stats")
async def stats(driver: Driver = Depends(get_driver)):
    with driver.session() as session:
        result = session.run("MATCH (n) RETURN count(n) AS total")
        record = result.single()
        return {"node_count": record["total"]}

@router.get("/documents")
async def list_documents(driver: Driver = Depends(get_driver)):
    with driver.session() as session:
        result = session.run("""
            MATCH (d:Document)
            OPTIONAL MATCH (d)-[:HAS_SECTION]->(s)
            RETURN d.name        AS doc_id,
                   d.title       AS title,
                   d.version     AS version,
                   d.issue_date  AS issue_date,
                   count(s)      AS section_count
            ORDER BY d.name
        """)
        return [dict(r) for r in result]