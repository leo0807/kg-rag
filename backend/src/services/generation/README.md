# services/generation — 规范文档智能生成工作流

## 文件地图
| 文件 | 职责 |
|------|------|
| `workflow.py` | 主流程协调：输入→结构分析→章节生成→校验→输出 |
| `structure_analyzer.py` | 分析用户描述，确定文档类型与必要章节 |
| `section_generator.py` | 按章节调用 LLM 逐段生成内容 |
| `validator.py` | 结构、引用、数值单位、术语四维自检校验 |
| `input_models.py` | Pydantic 输入模型（`DocGenRequest`） |
| `doc_exporter.py` | 将生成结果写出为 DOCX / PDF |

## 核心流程
```
POST /generation/generate
  → workflow.run(request)
      ├── structure_analyzer → 确定章节列表
      ├── section_generator  → 并发生成各章节
      ├── validator.validate_full() → 质量评分
      └── doc_exporter → 返回文件 URL
```

## 注意事项
- 并发章节生成受 `MAX_CONCURRENT_SECTIONS`（默认 4）控制
- `validator.py` 评分 < 60 时自动标记 `requires_human_review=true`
- 必需章节 §1 §2 §3 §6 §7 §8 缺失会扣 15 分/项（critical 问题）

## 测试
```bash
pytest tests/test_spec_validator.py -v
```
