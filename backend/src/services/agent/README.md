# services/agent — 智能体执行与工具调度

## 文件地图
| 文件 | 职责 |
|------|------|
| `agent_executor.py` | 主执行循环：接收问题 → 选工具 → 执行 → 聚合答案 |
| `tools.py` | 注册所有可用工具（图检索、向量检索、SQL 等） |
| `tool_executor.py` | 工具调用封装，统一异常处理与超时 |
| `agent_helpers.py` | 工具选择提示词构建、结果格式化辅助函数 |
| `agent_fallback.py` | 无结果时的降级策略（直接 LLM 回答） |
| `clarification.py` | 检测问题是否模糊，生成追问内容 |

## 核心流程
```
问题 → agent_executor.run()
  ├── clarification.py 判断是否需要追问
  ├── tools.py 选择工具集
  ├── tool_executor.py 并行/串行执行工具
  └── 聚合结果 → 若无结果则 agent_fallback.py 降级
```

## 注意事项
- 工具超时默认 15s，可通过 `AGENT_TOOL_TIMEOUT` 环境变量覆盖
- 工具列表在 `tools.py` 顶部注册，新增工具需同步更新
- fallback 会消耗额外 LLM token，监控时注意分开计费

## 测试
```bash
pytest tests/test_agent*.py -v
```
