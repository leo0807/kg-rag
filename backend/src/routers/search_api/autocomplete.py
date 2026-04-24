import logging
from fastapi import APIRouter, Depends, Query
from neo4j import Driver
from ...core.database import get_driver
from ...services.storage.es_store import search_sections_es

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["search"])

@router.get("/search/autocomplete")
async def autocomplete(
    q: str = Query(..., description="Search query"),
    driver: Driver = Depends(get_driver)
):
    """
    语义联想全域搜索：返回匹配的实体及其可能的关联关系路径。
    """
    # 1. 在 ES 中搜索匹配的实体 (目前主要搜 Section 和 Image)
    # TODO: 扩展 ES 索引以包含 Tool, Material 等实体名，目前先从 Section 中提取 doc_id
    es_results = search_sections_es(q, top_k=5)
    
    suggestions = []
    seen_entities = set()

    for res in es_results:
        # 实体建议
        entity_id = res["chunk_id"]
        if entity_id not in seen_entities:
            suggestions.append({
                "type": "entity",
                "label": res["title"] or res["number"] or entity_id,
                "id": entity_id,
                "entity_type": "Section",
                "doc_id": res["doc_id"]
            })
            seen_entities.add(entity_id)

    # 2. 如果 query 匹配到了特定的实体或文档，查询其 Neo4j 中的关系类型
    # 尝试直接在 Neo4j 中查找匹配的 Document 或其他实体名
    with driver.session() as session:
        # 搜索 Document, Tool, Material, Process 等
        # 这里使用比较简单的正则或包含匹配
        cypher = """
        MATCH (n)
        WHERE (n:Document AND (n.name CONTAINS $q OR n.title CONTAINS $q))
           OR (n:Tool AND n.name CONTAINS $q)
           OR (n:Material AND n.name CONTAINS $q)
           OR (n:Process AND n.name CONTAINS $q)
        WITH n LIMIT 5
        OPTIONAL MATCH (n)-[r]->()
        RETURN n.name AS name, labels(n)[0] AS type, collect(DISTINCT type(r)) AS rels
        """
        neo_results = session.run(cypher, q=q)
        
        for r in neo_results:
            name = r["name"]
            if name and name not in seen_entities:
                suggestions.append({
                    "type": "entity",
                    "label": name,
                    "id": name,
                    "entity_type": r["type"],
                    "relationships": r["rels"]
                })
                seen_entities.add(name)

    return {"suggestions": suggestions}
