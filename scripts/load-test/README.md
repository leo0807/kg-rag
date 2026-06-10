# KG-RAG 压测指南

## 安装

```bash
pip install locust
```

## 运行（Web UI）

```bash
locust -f scripts/load-test/locustfile.py --host http://localhost:8000
# 打开 http://localhost:8089 配置并发数和速率
```

## 无界面模式（自动化）

```bash
# 10并发，2/秒启动，跑60秒，结果写 CSV
locust -f scripts/load-test/locustfile.py \
       --host http://localhost:8000 \
       --headless -u 10 -r 2 --run-time 60s \
       --csv scripts/load-test/results/run_$(date +%Y%m%d_%H%M%S)
```

## 场景说明

| 接口              | 权重 | 说明                  |
|-------------------|------|-----------------------|
| POST /api/query/sync | 5  | 核心问答（最重要）    |
| GET  /api/search     | 3  | 全文搜索              |
| GET  /api/sessions   | 2  | 历史会话列表          |
| GET  /api/wiki/index | 1  | 规范百科首页          |
| GET  /api/health     | 1  | 健康检查              |

## 基准参考（单实例 4C8G）

- 非LLM接口（搜索、会话）：~200 RPS，p99 < 100ms
- 问答接口（含LLM调用）：~2 RPS，p99 < 30s（受LLM延迟限制）

## 扩容建议

- 搜索/历史接口成为瓶颈 → 增加 uvicorn workers（`--workers 4`）或横向扩容
- 问答接口成为瓶颈 → 增加 LLM 并发配额或接入多个 API Key 轮询
- Neo4j 成为瓶颈 → 升级到 Enterprise 版，启用读写分离
