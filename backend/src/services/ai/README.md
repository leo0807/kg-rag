# services/ai — AI 服务层

## 职责

统一管理 LLM 提供商（OpenAI-compat / Anthropic / 文心 / 本地模型），提供熔断、重试、Provider Pool 等可靠性机制。

## 文件地图

| 文件 | 职责 |
|------|------|
| `llm_service.py` | 单例入口 `get_llm_service()`，返回当前活跃 LLM 实例 |
| `service.py` | `LLMService` 基类：`chat(messages)` / `stream(messages)` |
| `llm.py` | 高层封装：带熔断+重试的 `chat()` |
| `circuit_breaker.py` | 状态机 CLOSED→OPEN→HALF_OPEN，防止级联故障 |
| `retry.py` | 指数退避重试装饰器 |
| `provider_pool.py` | 多 Provider 轮询/故障切换 |
| `_provider_factory.py` | 按 `settings.LLM_PROVIDER` 实例化对应 Provider |
| `providers/openai_compat.py` | OpenAI / DeepSeek / Qwen 等兼容接口 |
| `providers/anthropic.py` | Anthropic Claude 接口 |
| `providers/ernie.py` | 文心一言（百度）接口 |
| `errors.py` | LLM 统一异常类型 |
| `local_model_manager.py` | 本地模型加载管理（可选，不影响云端路径） |
| `local_router.py` | 本地模型路由（可选） |
| `finetune_data_collector.py` | 收集微调数据 |
| `finetuner.py` | 微调触发器 |

## 熔断器行为

```
CLOSED  ──(达到 failure_threshold)──►  OPEN
OPEN    ──(超过 reset_timeout_seconds)──►  HALF_OPEN
HALF_OPEN ──(probe 成功)──► CLOSED
HALF_OPEN ──(probe 失败)──► OPEN
```

配置项（`config.py`）：
- `LLM_CIRCUIT_BREAKER_THRESHOLD`（默认 5）
- `LLM_CIRCUIT_BREAKER_RESET_SECONDS`（默认 30）

重置：`reset_circuit_breaker()` 用于热重载配置后重建熔断器。

## 使用

```python
from src.services.ai.llm_service import get_llm_service

llm = get_llm_service()
reply = llm.chat([{"role": "user", "content": "你好"}])
```

## 测试

```bash
pytest tests/test_circuit_breaker.py tests/test_llm_errors.py tests/test_llm_retry.py -v
```
