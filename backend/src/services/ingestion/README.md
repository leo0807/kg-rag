# services/ingestion — 文档批量入库与重处理

## 文件地图
| 文件 | 职责 |
|------|------|
| `batch_ingest_service.py` | 批量上传任务调度：解析→向量化→图谱写入 |
| `reprocess_service.py` | 重处理单个文档（已入库文档重新提取） |
| `reprocess_orchestrator.py` | 重处理流程编排（多阶段协调） |
| `reprocess_pipelines.py` | 各阶段流水线定义 |
| `reprocess_support.py` | 重处理状态检查、前置条件验证 |
| `reprocess_vectorize.py` | 重处理时向量写回 Milvus |
| `snapshot_service.py` | 创建/恢复文档快照（灾备与回滚） |
| `backfill_service.py` | 历史数据回填（补充缺失的实体/向量） |
| `backfill_runtime.py` | 回填任务运行时（断点续跑） |
| `backfill_helpers.py` | 回填辅助：查询待处理记录、标记完成 |
| `processing_tracker.py` | 任务进度追踪（基于 task_state store） |

## 核心流程
```
POST /ingest/batch
  → batch_ingest_service.run_batch(files)
      ├── parsing → tables → entities
      ├── graph_write → Neo4j
      ├── vectorize → Milvus
      └── processing_tracker.update(status)
```

## 注意事项
- 重处理会先调用 `entity_graph_reset` 清空旧实体，再重新写入
- 快照存储路径由 `SNAPSHOT_DIR` 环境变量指定，默认 `/tmp/snapshots`
- 回填任务支持断点续跑：进度持久化于 `task_state` store

## 测试
```bash
pytest tests/test_ingest_task.py tests/test_reprocess_service.py tests/test_snapshot_service.py -v
```
