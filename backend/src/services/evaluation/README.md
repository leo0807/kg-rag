# services/evaluation — 评测体系

## 职责

对 RAG 回答质量做自动化评测，包括：客观题（选择/判断）、检索命中率基线、AB 测试、忠实性评估。

## 文件地图

### 客观题评测（objective_doc_eval_*）

| 文件 | 职责 |
|------|------|
| `objective_doc_eval_service.py` | HTTP 任务状态管理（启动/查询/重启） |
| `objective_doc_eval_runner.py` | `answer_objective_question()` 核心推理；`run_eval_task()` 异步批量 |
| `objective_doc_eval_retrieval.py` | 检索编排：stem_query + graph_augmented 两轮检索，`_get_do_retrieval()` 懒加载 |
| `objective_doc_eval_metrics.py` | 评分：`_apply_choice_support_override()`，证据支持度排序 |
| `objective_doc_eval_parser.py` | LLM 响应解析：`_parse_objective_llm_response()`，容错 JSON 提取 |
| `objective_doc_eval_parse_utils.py` | 解析工具函数 |
| `objective_doc_source_detection.py` | 检索命中率基线 |

**重要**：检索函数（`do_retrieval`）通过 `_get_do_retrieval()` 懒加载，避免循环依赖。
测试 mock 时 patch `src.services.evaluation.objective_doc_eval_retrieval._DO_RETRIEVAL`（私有，单下划线），不是 `objective_doc_eval_service.DO_RETRIEVAL`（不存在）。

### 其他评测

| 文件 | 职责 |
|------|------|
| `faithfulness_service.py` | 忠实性评分（答案是否有源文依据） |
| `ab_test_service.py` | 策略 A/B 对比测试 |
| `retrieval_harness_service.py` | 检索 harness（批量检索+评分） |
| `retrieval_harness_support.py` | Harness 辅助函数 |
| `dataset_eval_service.py` | 数据集评测入口 |
| `dataset_importer.py` | 题目数据集导入（Excel/JSON） |
| `dataset_schema.py` | 题目数据模型 |
| `baseline_report.py` | 基线报告生成 |
| `error_analyzer.py` | 错误类型分析 |
| `optimization_advisor.py` | 基于错误分析给出优化建议 |
| `eval_config.py` | 评测全局配置 |
| `eval_runner.py` | 通用评测 runner |

## 已知 Bug（需人工）

1. `core.py:145` 的早返回路径只返回 2-元组，但 `objective_doc_eval_retrieval.py:96` 解包 3 个值 → `ValueError`。
2. `context_utils.trim_conversation_history(history, max_rounds=0)` 返回完整历史（`-0` 切片 bug）。
3. `encryption._load_key()` hex 路径不可达：base64 先解码成功（但 len≠32）直接 return None，跳过 hex 分支。

## 测试

```bash
pytest tests/test_objective_doc_eval_service.py -v
```
