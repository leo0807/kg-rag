# services/storage — 向量/全文/图神经网络存储

## 文件地图
| 文件 | 职责 |
|------|------|
| `milvus_store.py` | Milvus 向量存储：写入、检索、Collection 管理 |
| `es_store.py` | Elasticsearch 全文索引：写入、BM25 检索 |
| `gnn_service.py` | 图神经网络特征计算与相似度检索 |

## 核心流程
```
文档向量化:
  → milvus_store.upsert(section_id, embedding, metadata)
  → es_store.index(section_id, text, metadata)

混合检索:
  → milvus_store.search(query_vec, top_k) → [(id, score)]
  → es_store.search(query_text, top_k)    → [(id, score)]
  → RRF 融合 → 最终排序
```

## 注意事项
- Milvus Collection 在首次写入时自动创建（`ensure_milvus_connected`）
- ES 索引名通过 `settings.ES_INDEX` 配置，默认 `kg_sections`
- `gnn_service` 依赖 PyTorch Geometric，未安装时该模块不可用（不影响其他检索）
- **已知问题**: pymilvus 与 NumPy 2.x 不兼容，需 NumPy < 2.0（需人工）

## 测试
```bash
pytest tests/test_milvus_store.py -v
```
