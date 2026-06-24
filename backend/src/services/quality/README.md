# services/quality — 规范冲突与工件缺陷检测

## 文件地图
| 文件 | 职责 |
|------|------|
| `conflict_detector.py` | 公共接口：列表查询、状态更新、统计 |
| `conflict_scan.py` | 扫描任务管理：启动/查询/列出扫描 |
| `conflict_detectors.py` | 具体检测规则（约束检测 + LLM 语义检测） |
| `conflict_arbiter.py` | 多路检测结果仲裁（去重、置信度合并） |
| `defect_detector.py` | 工件视觉缺陷检测（YOLO / VLM 降级） |
| `defect_writer.py` | 将缺陷检测结果写入 DB 和 Neo4j |
| `feedback_optimizer.py` | 根据用户反馈优化检测模型参数 |

## 核心流程
```
规范冲突扫描:
  POST /quality/conflicts/scan
    → start_conflict_scan(db, driver, scan_id)
        ├── constraint 检测 (conflict_detectors.py)
        ├── semantic 检测 (LLM)
        └── conflict_arbiter 合并结果 → ConflictRecord[]

工件缺陷:
  POST /quality/defects/detect
    → defect_detector.detect_defects(image_path)
        ├── YOLO（若可用）
        └── VLM 降级（detect_defects_vlm）
```

## 注意事项
- YOLO 权重路径通过 `set_model_path()` 或 `YOLO_WEIGHTS_PATH` 环境变量指定
- 冲突状态流转：`pending → confirmed / dismissed / resolved`
- `feedback_optimizer` 目前为存根，实际模型微调需人工触发

## 测试
```bash
pytest tests/test_defect_detector.py -v
```
