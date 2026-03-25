import logging
from fastapi import APIRouter, Depends
from neo4j import Driver
from ..core.database import get_driver

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["graph"])

@router.get("/graph")
async def get_graph(driver: Driver = Depends(get_driver)):
    with driver.session() as session:
        nodes_result = session.run("""
            MATCH (n)
            RETURN elementId(n) AS id,
                   labels(n)[0] AS label,
                   coalesce(n.name, n.title, n.chunk_id) AS name
            LIMIT 100
        """)
        nodes = [dict(r) for r in nodes_result]
        node_ids = {n["id"] for n in nodes}

        edges_result = session.run("""
            MATCH (a)-[r]->(b)
            RETURN elementId(a) AS source,
                   elementId(b) AS target,
                   type(r)      AS type
            LIMIT 300
        """)
        edges = [
            dict(r) for r in edges_result
            if r["source"] in node_ids and r["target"] in node_ids
        ]

    return {"nodes": nodes, "edges": edges}