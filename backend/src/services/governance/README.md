# services/governance — 数据治理体系

## 文件地图
| 文件 | 职责 |
|------|------|
| `data_quality.py` | 文档质量检查：空内容、缺标题、重复文件名 |
| `compliance_report.py` | 合规报告生成 + 异常行为检测（暴力登录/批量删除） |
| `content_moderator.py` | 内容安全审核（敏感词、危险指令过滤） |
| `lifecycle_runner.py` | 文档生命周期调度：到期提醒、归档、清理 |

## 核心流程
```
GET /governance/quality-report
  → get_quality_summary(db)
      └── check_document_quality(db) → issues[]

GET /governance/compliance-report?days=30
  → generate_report(db, days=30)
      ├── 汇总审计事件统计
      └── detect_anomalies(db) → 最近1小时异常
```

## 注意事项
- 异常检测阈值（`_ANOMALY_THRESHOLDS`）可在代码内调整，暂无配置化
- `lifecycle_runner` 建议通过 Celery Beat 调度，非同步 HTTP 调用
- `content_moderator` 使用关键词列表，不依赖 LLM，调用延迟极低

## 测试
```bash
pytest tests/test_data_quality.py tests/test_compliance_report.py -v
```
