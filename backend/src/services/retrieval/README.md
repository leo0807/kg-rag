# services/retrieval — 检索层

## 职责

向量检索（Milvus）、全文检索（Elasticsearch）、图谱增强检索（Neo4j）、重排序、查询扩展、HyDE 等，组合为不同检索策略供 `routers/query` 调用。

## 文件地图

| 文件 | 职责 |
|------|------|
| `retriever.py` | 核心向量检索：`VectorRetriever.search()` |
| `parallel_search.py` | 并行策略：向量 + 全文同时检索，按分数合并 |
| `multi_hop.py` | 多跳图谱扩展检索 |
| `multi_hop_support.py` | 多跳辅助函数 |
| `embedder.py` | `embed_texts()` 封装，调用 embedding 服务 |
| `embedding_service.py` | HTTP embedding 服务适配层 |
| `reranker.py` | Cross-encoder 重排序（依赖 sentence-transformers） |
| `query_expander.py` | 近义词扩展：文件字典 + Neo4j SYNONYM_OF 关系 |
| `hyde_service.py` | HyDE（假设文档嵌入）查询增强 |
| `semantic_cache.py` | 语义缓存（embedding 相似度命中） |
| `semantic_linker.py` | 章节语义链接 |
| `compare_query.py` / `compare_summary.py` / `compare_images.py` | 多文档比较检索 |
| `counterfactual.py` / `counterfactual_intent.py` | 反事实意图识别 |
| `multimodal_search.py` | 图文联合检索 |
| **`neo4j_cache.py`** | 可选 Neo4j 查询缓存（默认禁用，零侵入） |

## 检索策略

| 策略名 | 描述 |
|--------|------|
| `parallel` | 向量 + 全文并行，RRF 融合，**默认策略** |
| `graph_augmented` | parallel 基础上追加图谱邻居扩展 |
| `multi_hop` | 多跳子图遍历，适合关系推理类问题 |
| `semantic` | 纯语义相似度 |

## Neo4j 查询缓存（可选）

`neo4j_cache.py` 提供进程内 LRU + TTL 缓存，**默认不启用**：

```bash
ENABLE_NEO4J_QUERY_CACHE=true  # 启用
NEO4J_CACHE_TTL_SECONDS=60     # 默认 60s
NEO4J_CACHE_MAX_ENTRIES=256    # 默认 256 条
```

```python
from src.services.retrieval.neo4j_cache import cached_session

with cached_session(driver, ttl=30) as session:
    result = session.run("MATCH (d:Document) RETURN d.name LIMIT 10")
```

写查询（含 CREATE/MERGE/SET/DELETE）自动跳过缓存。

## 注意事项

- `reranker.py` 依赖 `sentence-transformers`，conda 环境中 numpy 2.x 与 scipy 不兼容，会导致导入失败。Docker 环境正常。
- `query_expander.expand_query()` 使用正则 `[一-龥]{2,}` 按连续 CJK 字符提取词条，词条中无标点分隔时整句为一个 token。

## 测试

```bash
pytest tests/test_retrieval_strategies.py tests/test_query_expander.py tests/test_neo4j_cache.py -v
```
