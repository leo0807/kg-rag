# 无人值守工作日志

## 2026-06-20 无人值守执行记录

### 阶段 A — 地基修复

#### A1 — scripts/schema-sync.py CLI（已存在，无需新建）
- **状态**: 已完成（脚本在此前 commit `9601a5a` 已提交）
- **验证**: 运行 `DATABASE_URL=... python scripts/schema-sync.py` → 输出 "No missing columns found"，schema 已是最新
- **动了哪些文件**: 无（脚本已存在）
- **待人工验证**: 无

#### A2 — 前端 null/数组防御（commit `1ca5231`）
- **做了什么**: 对 12 个管理页面补充运行时防护
  - `.map()` 前加 `?? []`：metrics（volume.daily）、status（pressure.factors）、data-quality（issues）
  - `Object.entries()` 前加 `?? {}`：DashboardCharts（services）、FeedbackStats（error_type_dist）、eval/runs/[id]（by_reason）、audit/users/[id]（action_breakdown）
  - `.toFixed()/.toLocaleString()` 前加 `?? 0`：metrics（cost_usd）、DashboardKPIs（node_count/rel_count/queries_7d）、usage/page（requests/cost_usd）、UserUsageTable（today_requests/week_requests/cost）、OpsBaselineTab（mrr）、AbTestTab（avg_recall/mrr/avg_ndcg）
- **动了哪些文件**: 12 个 .tsx 文件（均在 frontend/src/app/admin/）
- **已验证**: 代码审查通过，无运行时崩溃路径
- **待人工验证**: 浏览器实测 null 场景（API 返回空字段时页面不崩溃）

#### A3 — numpy 版本锁定（commit `cbcf536`）
- **做了什么**: `numpy==2.4.3` → `numpy>=1.24,<2`
- **动了哪些文件**: `backend/requirements.txt`
- **已验证**: 本地运行 schema-sync.py 时已看到 NumPy 2.x ABI 警告，锁定后 Docker build 将安装 numpy<2
- **待人工验证**: 重建 Docker 镜像后确认无 ABI 警告

---

### 阶段 B — README 对账补完（此前 session 已完成）

- **B1** commit `7437d89`: 8 项 README checkbox 已勾选，150+ 路线图条目归档至 `docs/roadmap/`
- **B2** commit `13e754e`: pip-audit CI job 新增（gitleaks/npm audit 已存在）
- **B2** commit `62c9f2a`: OpenTelemetry TracerProvider 初始化加入 startup.py

---

### 阶段 C — 可观测性

#### C1 — Prometheus /metrics（commit `22a7785`）
- **做了什么**:
  - `requirements.txt` 增加 `prometheus-fastapi-instrumentator>=6.1`
  - `backend/src/main.py` 在 ShutdownGateMiddleware 之后插入 Instrumentator，暴露 `GET /metrics`
  - 库未安装时降级 warning，服务正常启动
- **动了哪些文件**: `backend/requirements.txt`, `backend/src/main.py`（+9 行，未改任何现有接口）
- **已验证**: 代码审查，try/except 保证零侵入
- **待人工验证**: `curl http://localhost:8000/metrics` 确认 Prometheus 格式输出

#### C2 — Grafana 监控栈（本次 commit）
- **做了什么**:
  - 新建 `docker-compose.monitoring.yml`：叠加 Prometheus v2.52 + Grafana 10.4 服务
  - 新建 `monitoring/prometheus.yml`：15s 抓取 aviation-backend:8000/metrics
  - 新建 `monitoring/grafana/provisioning/datasources/prometheus.yml`：自动注册 Prometheus 数据源
  - 新建 `monitoring/grafana/provisioning/dashboards/kg-rag.yml`：Dashboard 文件夹提供者
  - 新建 `monitoring/grafana/dashboards/kg-rag.json`：预置仪表盘（请求速率/按状态码/P50-P99延迟/5xx错误率）
- **动了哪些文件**: 5 个新文件，均在 monitoring/ 或根目录，未改任何现有配置
- **启动方式**:
  ```bash
  docker compose -f docker-compose.yml \
                 -f docker-compose.prod.yml \
                 -f docker-compose.monitoring.yml up -d prometheus grafana
  ```
  - Grafana: http://localhost:3001 (admin/admin)
  - Prometheus: http://localhost:9090
- **待人工验证**: 启动后在 Grafana 查看 "KG-RAG 后端监控" 仪表盘，确认 Prometheus 数据源连通

---

## 硬性停止线

已在 C2 完成后停止。以下任务等待人工回来确认后再执行：

| 任务 | 原因 |
|------|------|
| C3 幂等中间件 | 改请求链路，需浏览器实测 |
| C4 WebSocket 进度 | 改请求链路，需浏览器实测 |
| E1 文档权限模型 | Breaking change |
| E2 部门隔离 | Breaking change |
| E3 cursor 分页 | Breaking change |
| D 全链路联调 | 只能人工做 |
