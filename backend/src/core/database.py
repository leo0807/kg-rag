import logging
from neo4j import GraphDatabase
from .config import settings

logger = logging.getLogger(__name__)
_driver = None

def get_driver():
    return _driver

def init_db():
    global _driver
    _driver = GraphDatabase.driver(
        settings.NEO4J_URI,
        auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
    )
    _driver.verify_connectivity()
    logger.info("Neo4j Connection Successfull")
    print(">>> lifespan 启动：数据库连接已建立")