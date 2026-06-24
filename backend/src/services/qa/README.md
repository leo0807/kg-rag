# services/qa — 问答策略路由与题型处理

## 文件地图
| 文件 | 职责 |
|------|------|
| `strategy_router.py` | 根据问题类型路由到对应检索策略 |
| `question_handlers.py` | 处理不同问题类型（数值/流程/比较/是否题） |
| `question_recommender.py` | 基于当前上下文推荐相关追问 |
| `term_linker.py` | 将问题中的术语链接到术语表节点 |
| `mcq_handler.py` | 多选题处理（选项提取、答案验证） |
| `mcq_elimination.py` | 排除法辅助多选题推理 |
| `mcq/` | MCQ 子模块（题库管理、批量生成） |

## 核心流程
```
用户问题 → strategy_router.route(question)
  ├── 数值类 → graph_cypher 策略
  ├── 流程类 → hybrid 策略（向量 + 图）
  ├── 比较类 → multi_doc 策略
  └── MCQ   → mcq_handler.handle()
       └── mcq_elimination 排除干扰项
```

## 注意事项
- 策略路由基于简单关键词匹配 + LLM 分类，分类错误时回退到 `hybrid`
- `term_linker` 需要 Neo4j 连接，离线时跳过术语链接步骤
- MCQ 答案验证不依赖 LLM，纯规则匹配，延迟 < 5ms

## 测试
```bash
pytest tests/test_strategy_router.py tests/test_mcq_utils.py -v
```
