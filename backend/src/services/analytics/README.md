# services/analytics — 业务洞察与报告引擎

## 文件地图
| 文件 | 职责 |
|------|------|
| `insights_engine.py` | 汇总用户行为、质量、知识库、运维四大维度指标 |
| `nl_to_sql.py` | 自然语言转 SQL 查询，用于自定义数据分析 |
| `report_engine.py` | 报告生成调度器，整合多个数据源 |
| `report_templates.py` | 报告模板定义（Jinja2 / 字典结构） |
| `pdf_report.py` | 将报告数据渲染为 PDF（依赖 WeasyPrint/ReportLab） |

## 核心流程
```
GET /analytics/insights?period=30d
  → InsightsEngine.usage_insights(db)
      ├── _count_active_users()
      ├── _query_trend()
      ├── _top_questions()
      └── _engagement_metrics()
  → 返回聚合 dict（无需 Neo4j）
```

## 注意事项
- `insights_engine` 全部读 `audit_logs` 表，需确保审计日志已启用
- `nl_to_sql` 依赖 LLM 生成 SQL，结果需经白名单过滤防注入
- PDF 导出依赖 WeasyPrint，生产环境需安装 GTK 库

## 测试
```bash
pytest tests/test_insights_engine.py -v
```
