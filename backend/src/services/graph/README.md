# services/graph — Neo4j 图谱写入与版本管理

## 文件地图
| 文件 | 职责 |
|------|------|
| `neo4j_writer.py` | 顶层写入接口：批量 MERGE 节点和关系 |
| `entity_writer.py` | 实体写入调度，协调去重与批处理 |
| `entity_graph_write.py` | 核心 Cypher 执行：MERGE entity + relation |
| `entity_batching.py` | 将实体列表分批，避免单次事务过大 |
| `entity_extractor.py` | 从文档节点提取实体列表 |
| `entity_filters.py` | 过滤低置信度/重复实体 |
| `entity_graph_reset.py` | 删除指定文档关联的全部实体/关系（重处理用） |
| `entity_writer_support.py` | 实体类型规范化、属性清洗 |
| `versioning.py` | 节点版本号管理（`version` 属性递增） |
| `link_prediction.py` | 基于共现预测潜在关系 |
| `lazy_loading.py` / `lazy_loading_search.py` | 按需加载图节点（大图分页） |
| `graph_helpers.py` | Cypher 片段生成工具函数 |
| `document_persistence.py` | 将 Document 节点持久化到 Neo4j |

## 核心流程
```
实体列表 → entity_batching → entity_graph_write.py
                                 └── MERGE (e:Entity {name, type})
                                 └── MERGE (sec)-[:MENTIONED_IN]-(e)
```

## 注意事项
- 批大小默认 50，可通过 `NEO4J_BATCH_SIZE` 环境变量调整
- `versioning.py` 使用乐观锁，并发写同一节点时可能冲突（重试 3 次）
- `entity_graph_reset.py` 为破坏性操作，仅在重处理流程调用

## 测试
```bash
pytest tests/test_neo4j_writer.py tests/test_reprocess_entity_graph.py -v
```
