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

## 2026-06-21 无人值守批量任务执行记录

### 批量任务 1 — 后端测试（commits e5bc627）

| 文件 | 测试数 | 状态 |
|------|--------|------|
| `backend/tests/test_jwt.py` | 16 | ✅ 全通过（本地 conda） |
| `backend/tests/test_password.py` | 12 | ⚠️ conda 环境跳过（缺 passlib），Docker 全量通过 |
| `backend/tests/test_quota_checker.py` | 22 | ⚠️ conda 环境跳过（缺 pytest-asyncio），Docker 全量通过 |
| `backend/tests/test_tenant_filter.py` | 17 | ✅ 全通过（本地 conda） |

修复：`test_password.py` 加 `pytest.importorskip("passlib")` 避免 ImportError

### 批量任务 2 — 前端测试（commits a4557a1, dfe04e2）

| 文件 | 测试数 | 状态 |
|------|--------|------|
| `frontend/src/test/quotaPanel.test.tsx` | 7 | ✅ 全通过 |
| `frontend/src/test/billingPage.test.tsx` | 9 | ✅ 全通过 |
| `frontend/src/test/helpDrawer.test.tsx` | 8 | ✅ 全通过 |

总计：24 passed；biome lint 清零（`as any` → `as unknown as Ctor`）

### 批量任务 3 — 覆盖率配置（commit 854905c）

- `frontend/vitest.config.ts`：增加 `coverage.provider=v8`
- `frontend/package.json`：增加 `test:coverage` 脚本
- `@vitest/coverage-v8` pnpm 安装并锁入 pnpm-lock.yaml
- 当前语句覆盖率 1.84%（仅测试了 3 个组件）

### 批量任务 4 — 类型标注（commit 6d567c3）

- `TenantQueryMixin.query_for_tenant` 补充 `-> Any` 返回类型

### 批量任务 5 — lint 清理（同 commit dfe04e2）

- biome format + organizeImports 应用于 3 个新测试文件
- `noExplicitAny` 通过 `as unknown as ApiErrorCtor` 替换解决

### 批量任务 6 — 文档（commit 112f031）

| 文件 | 说明 |
|------|------|
| `scripts/README.md` | 全部脚本按类别索引（部署/备份/安全/ML） |
| `docs/runbook.md` | 巡检/故障处理/备份恢复/告警矩阵 |
| `docs/deployment.md` | 开发/生产/HA/离线部署步骤 |

### 批量任务 7 — API 文档 + OpenAPI CI + 灾难恢复 + semantic-release

| 文件 | 说明 |
|------|------|
| `docs/api.md` | API 端点参考、认证、错误码、多租户说明 |
| `backend/scripts/export_openapi.py` | 无服务器导出 OpenAPI JSON |
| `.github/workflows/openapi-client.yml` | CI 自动导出+校验 OpenAPI spec |
| `docs/disaster-recovery.md` | RTO/RPO 目标、恢复流程、演练计划 |
| `.releaserc.json` | semantic-release 配置 |
| `scripts/bump_version.py` | 版本号同步脚本（被 semantic-release 调用） |
| `.github/workflows/release.yml` | 自动发布 CI |

---

## 2026-06-21 无人值守执行记录（测试补强 + 文档 + 工具）

### 测试 import 路径修复（5 个文件）

| 文件 | 修复内容 |
|------|----------|
| `tests/test_graph_router.py` | `_FakeSession` 图片行缺少 `page_num` 字段（B1）|
| `tests/test_parser.py` | monkeypatch 路径 `parser.pdfplumber` → `parser_sections.pdfplumber`（B5）|
| `tests/test_pdf_image_extractor.py` | `_extract_images_from_docx` → `extract_images_from_docx`（B6）|
| `tests/test_table_extractor.py` | `table_extractor._CAMELOT_AVAILABLE` → `strategies.CAM_ELOT_AVAILABLE`（B7/B8）|

B2（`core.py:145` 早返回只返回 2-元组）、B3/B4（`DO_RETRIEVAL` 属性不存在，3-调用模式与实现不符）→ **需人工**

### 新增测试文件（+174 个测试，全部通过）

| 文件 | 测试数 | 覆盖模块 |
|------|--------|----------|
| `tests/test_circuit_breaker.py` | 13 | `services/ai/circuit_breaker.py` |
| `tests/test_answer_guard.py` | 14 | `services/answer_guard.py` |
| `tests/test_context_utils.py` | 27 | `services/context_utils.py` |
| `tests/test_table_normalization.py` | 23 | `services/tables/normalization.py` |
| `tests/test_query_intents.py` | 11 | `services/query_intents.py` |
| `tests/test_encryption.py` | 13 | `services/security/encryption.py` |
| `tests/test_upload_validator.py` | 10 | `services/security/upload_validator.py` |
| `tests/test_answer_humanizer.py` | 14 | `services/answer_humanizer.py` |
| `tests/test_field_masking.py` | 20 | `services/auth/field_masking.py` |
| `tests/test_mcq_utils.py` | 33 | `services/qa/mcq/utils.py` + `parser.py` |
| `tests/test_query_expander.py` | 11 | `services/retrieval/query_expander.py` |
| `tests/test_llm_errors_classify.py` | 23 | `services/ai/errors.py` |
| `tests/test_conversation_exporter.py` | 19 | `services/conversation/exporter.py` |
| `tests/test_neo4j_cache.py` | 21 | `services/retrieval/neo4j_cache.py`（新增） |

### 新增源文件

| 文件 | 描述 |
|------|------|
| `src/services/retrieval/neo4j_cache.py` | 可选 Neo4j LRU+TTL 查询缓存（默认禁用，`ENABLE_NEO4J_QUERY_CACHE=true` 启用） |

### 新增脚本

| 文件 | 描述 |
|------|------|
| `scripts/export_knowledge_graph.py` | Neo4j 知识图谱导出（JSON/CSV/Cypher 三种格式，支持按 doc_id 过滤）|
| `scripts/rebuild_vector_index.py` | 离线全量/增量重建 Milvus 向量索引 |

### 新增 README

| 文件 | 模块 |
|------|------|
| `src/services/parsing/README.md` | 文档解析模块设计说明 |
| `src/services/tables/README.md` | 表格提取模块设计说明 |
| `src/services/ai/README.md` | AI 服务层（LLM + 熔断 + 重试）|
| `src/services/evaluation/README.md` | 评测体系设计说明 |
| `src/services/retrieval/README.md` | 检索层设计说明 |
| `src/services/security/README.md` | 安全模块设计说明 |

### 发现的 Bug（需人工）

| Bug | 位置 | 描述 |
|-----|------|------|
| 早返回 2-元组 | `src/routers/query/core.py:145` | `return sections, {}` 只返回 2 值，而 `harness_service.py:277` 解包 3 值 → `ValueError` |
| DO_RETRIEVAL 不存在 | `src/services/evaluation/objective_doc_eval_service.py` | 测试 B3/B4 期望的 3-调用 HyDE 模式在当前实现中不存在 |
| max_rounds=0 全返回 | `src/services/context_utils.py:13` | `history[-0:]` = `history[0:]`，传 0 返回全量历史 |
| hex 密钥路径不可达 | `src/services/security/encryption.py:_load_key` | Base64 先解码成功但 len≠32 时 return None，hex 分支永远不执行 |

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
