import logging
from .config import settings
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from neo4j import Driver

logger = logging.getLogger(__name__)
_driver = None

def get_driver() -> "Driver":
    if _driver is None:
        raise RuntimeError("Neo4j 未初始化，请检查数据库连接")
    return _driver

_SCHEMA_STATEMENTS = [
    # 唯一性约束（自动创建索引）
    "CREATE CONSTRAINT document_name IF NOT EXISTS FOR (d:Document) REQUIRE d.name IS UNIQUE",
    "CREATE CONSTRAINT section_chunk_id IF NOT EXISTS FOR (s:Section) REQUIRE s.chunk_id IS UNIQUE",
    # 向量索引（bge-m3 输出 1024 维，余弦相似度）
    """
    CREATE VECTOR INDEX section_embedding IF NOT EXISTS
    FOR (s:Section) ON (s.embedding)
    OPTIONS {indexConfig: {
        `vector.dimensions`: 1024,
        `vector.similarity_function`: 'cosine'
    }}
    """,
]

def _init_schema(driver):
    with driver.session() as session:
        for stmt in _SCHEMA_STATEMENTS:
            session.run(stmt)
    logger.info("Neo4j schema 初始化完成")

def init_db():
    global _driver
    from neo4j import GraphDatabase
    _driver = GraphDatabase.driver(
        settings.NEO4J_URI,
        auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
    )
    _driver.verify_connectivity()
    _init_schema(_driver)
    logger.info("Neo4j Connection Successfull")
    print(">>> lifespan 启动：数据库连接已建立")
