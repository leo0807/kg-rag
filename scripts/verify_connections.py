# 目标：验证 Neo4j 和 Milvus 都能从 Python 连通

from neo4j import GraphDatabase
from pymilvus import connections, utility

# ── 1. 连接 Neo4j ──────────────────────────────
# Neo4j 用 Bolt 协议，类似 MySQL 的 TCP 连接
# GraphDatabase.driver 是长连接，程序里只创建一次

driver = GraphDatabase.driver(
    "bolt://localhost:7687",
    auth=("neo4j", "aviation123")
)

with driver.session() as session:
    result = session.run("RETURN 'Neo4j 连接成功！' AS msg")
    print(result.single()["msg"])

driver.close()

# ── 2. 连接 Milvus ─────────────────────────────
# Milvus 用 gRPC 协议，connections.connect 是全局注册
# 不像 Neo4j 返回一个对象，而是注册一个别名

connections.connect(
    alias="default",        # 给这个连接起个名字
    host="localhost",
    port="19530"
)

print(f"Milvus 连接成功！服务器版本：{utility.get_server_version()}")