# services/conversation — 对话会话管理与导出

## 文件地图
| 文件 | 职责 |
|------|------|
| `exporter.py` | 将对话历史导出为 Markdown / JSON / DOCX 格式 |

## 核心流程
```
POST /conversations/{id}/export?format=markdown
  → exporter.export(session_id, format)
      └── 读取会话轮次 → 格式化 → 返回文件流
```

## 注意事项
- 导出前会调用 `pii_masker` 对话轮次中的 PII 字段脱敏
- DOCX 导出依赖 `python-docx`，未安装时自动降级为 Markdown
- 大型会话（>500 轮）建议后台异步导出，避免超时

## 测试
```bash
pytest tests/test_conversation_exporter.py -v
```
