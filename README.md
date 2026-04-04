# CPS 知识库 — 航空工艺规范 GraphRAG 系统

> 基于知识图谱与向量检索融合的航空制造工艺规范智能问答系统

## 系统架构
```
PDF 文件
   ↓ ETL 解析（pdfplumber + 正则）
Neo4j 图谱 ←→ Milvus 向量库
   ↓ 并行检索（全文 + 向量）+ RRF 融合 + Reranker 精排
FastAPI 后端
   ↓ LLM 答案生成（OpenAI 兼容 API）
Next.js 前端（用户认证 + 会话管理）
```

## 功能特性

**智能问答**
- 两阶段检索：并行（全文+向量）→ RRF 融合 → bge-reranker 精排
- LLM 答案生成，支持 OpenAI 兼容 API / Anthropic
- 来源溯源，引用章节可点击跳转
- 会话管理，历史记录持久化到 Neo4j

**文档管理**
- PDF 批量导入，断点续传
- 自动解析文档编号、版本、章节结构、引用关系
- 章节内容展开和全文搜索高亮

**用户系统**
- JWT 认证，6位工号登录
- 个人资料管理（姓名、部门、邮箱）
- 密码修改
- 管理员用户管理（启用/禁用、权限管理）
- 用户配置（模型选择、检索策略）

**知识图谱可视化**
- D3.js 力导向图，边颜色区分关系类型
- 节点/边类型过滤，缩放和重置
- 点击跳转文档详情

**工程特性**
- API 限流（查询 30次/分钟，导入 10次/分钟）
- 自托管 Langfuse LLMOps 可观测性
- Docker Compose 一键启动全栈
- 24 个单元/集成测试

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Next.js 15 · TypeScript · Tailwind CSS · D3.js |
| 后端 | FastAPI 0.115 · Python 3.12 · Pydantic v2 |
| 图数据库 | Neo4j 5.20 |
| 向量数据库 | Milvus 2.4 |
| 关系数据库 | PostgreSQL 15 |
| 缓存 | Redis 7 |
| Embedding | BAAI/bge-m3（本地）|
| Reranker | BAAI/bge-reranker-v2-m3（本地）|
| LLM | OpenAI 兼容 API（硅基流动/Ollama/vLLM）|
| 可观测性 | Langfuse 2（自托管）|
| 容器化 | Docker Compose |

## 快速启动

### 前置条件
- Docker Desktop
- conda
- Node.js 20+

### 第一步：启动基础服务
```bash
docker compose up -d
```

| 服务 | 地址 |
|------|------|
| Neo4j Browser | http://localhost:7474 |
| Milvus Attu | http://localhost:8080 |
| Langfuse | http://localhost:3001 |

### 第二步：配置环境变量

复制 `.env.example` 为 `.env`，填入配置：
```bash
cp .env.example .env
```

关键配置：
```
LLM_API_URL=https://api.siliconflow.cn/v1
LLM_API_KEY=sk-xxx
LLM_MODEL=Qwen/Qwen2.5-7B-Instruct
```

### 第三步：启动后端
```bash
conda activate kg-rag
cd backend
python -m uvicorn src.main:app --reload --port 8000
```

### 第四步：启动前端
```bash
cd frontend
npm run dev
```

访问 http://localhost:3000，使用默认管理员账号登录。

### 默认管理员账号

后端**首次启动时**会自动检测数据库是否为空，若无任何用户则自动创建默认管理员：

| 字段 | 值 |
|------|----|
| 工号（用户名） | `000001` |
| 密码 | `admin123` |

直接访问 http://localhost:3000/login 使用上述账号登录即可。

> ⚠️ 生产环境请登录后前往「设置 → 修改密码」更改默认密码。

### 登录错误说明

| 错误提示 | 原因 | 解决方法 |
|----------|------|----------|
| 该工号不存在，请联系管理员开通账号 | 输入的工号在系统中不存在 | 联系管理员创建账号 |
| 密码错误，请重试 | 工号存在但密码不正确 | 重新输入密码或申请重置 |
| 账号已被禁用 | 账号被管理员停用 | 联系管理员恢复 |

### 忘记密码 / 密码重置

本系统**不支持邮件自助找回密码**，请通过以下流程重置：

**用户操作：**
1. 在登录页点击「忘记密码？」查看说明
2. 记录自己的 6 位工号，联系系统管理员

**管理员操作：**
1. 登录系统，进入「设置 → 用户管理」
2. 找到目标用户，点击「重置密码」
3. 输入临时密码后确认，告知用户
4. 用户登录后应立即前往「设置 → 修改密码」更改临时密码

### 批量导入 PDF
```bash
cd backend
python scripts/batch_ingest.py --dir /path/to/pdf/folder --skip-existing
```

## 运行测试
```bash
cd backend
python -m pytest tests/ -v
```

## 未来计划

- [x] LangGraph 多跳推理 Agent
- [x] 浅色/深色主题切换
- [x] 移动端适配
- [ ] Kubernetes 部署

## 未来计划（续）

- [x] 数据飞轮：查询结果评分 → 收集高质量问答对 → 微调 Reranker
- [x] Token 刷新机制
- [x] CORS 配置
- [x] 错误边界组件
- [x] 串行/多跳推理策略完整实现

## 长期规划

### 多模态知识图谱
- [x] PDF 图片提取（pdfplumber + pymupdf）
- [x] 图片多模态理解（GPT-4V / Qwen-VL）提取图中的工艺步骤、工具、尺寸数据
- [x] 图文关联：Section 节点关联 Image 节点，图片描述写入向量库
- [x] 多模态查询：用户可以上传图片提问（支持粘贴/点击上传，图片随消息持久化）
- [x] 知识图谱扩展：Tool / Material / Process 节点，LLM 实体提取 + Neo4j 写入

### 数据飞轮
- [x] 查询结果 👍/👎 评分
- [x] 点击来源章节记录隐式反馈（`detail` 字段存储 `clicked_source:<chunk_id>`）
- [x] 高质量问答对收集 → 微调 Reranker（`/api/feedback/export` + `scripts/export_training_data.py`）

### 其他
- [x] 多跳推理（LangGraph Agent）
- [x] 流式输出（SSE）
- [x] WebSocket 导入进度推送
- [x] 前端单元测试（Vitest）
- [x] 全局跨文档搜索
- [x] 文档对比功能
- [x] 知识图谱整体拖拽平移（svg.call(zoom) 绑定）

---

## 待完善清单（经代码审查整理）

### 知识图谱增强

**节点与关系扩展**
- [x] Tool / Material / Process 节点间关系：`REQUIRES_TOOL`（Process→Tool）、`USES_MATERIAL`（Process→Material）、`ALTERNATIVE_TO`、`COMPATIBLE_WITH`
- [x] 文档版本溯源：`SUPERSEDES` / `OBSOLETED_BY` 关系；章节级变更检测 `ADDED_SECTION` / `REMOVED_SECTION` / `CHANGED_TO`
- [x] 工艺约束节点：LLM 提取力矩/公差/温度/压力等参数，写入 `Constraint` 节点，`(Section)-[:HAS_CONSTRAINT]->(Constraint)`
- [x] 跨文档语义边：`SIMILAR_TO {score}` 关系，离线脚本 `scripts/build_semantic_links.py`，API `POST /api/graph/semantic-links`
- [x] 图谱统计 API：`GET /api/stats/knowledge-graph` 返回节点数量、关系数量、各维度覆盖率

**图谱可视化**
- [x] 图谱节点数量限制可配置（当前 Document:50 / Section:200 / Image:100 均硬编码）
- [x] Tool / Material / Process 节点加入可视化及过滤（实体已写入 Neo4j，前端尚未渲染）
- [x] 节点详情侧边栏：点击任意节点展开属性面板，而非仅 tooltip
- [x] 图谱导出：支持导出为 JSON/GraphML，供 Gephi 等工具进一步分析
- [x] 支持按文档 `doc_id` 筛选，只展示单个规范的子图

**实体质量**
- [x] 实体去重与归一化：当前用名称 MERGE，"液压泵" 与 "液压系统泵" 会产生冗余节点，需同义词合并
- [x] 实体审核页面：管理员可以查看、合并、删除自动提取的 Tool/Material/Process 节点

---

### 检索与推理增强

**查询策略**
- [x] 实体感知检索：查询时提取问题中的工具/材料名，优先召回含对应 `REQUIRES_TOOL` / `USES_MATERIAL` 边的章节
- [x] 自动策略选择：根据问题类型（定义型/步骤型/对比型/约束型）自动选择检索策略，无需用户手选
- [x] 图谱增强策略延伸 Tool/Material/Process：当前 `graph_augmented` 仅展开 `HAS_SUBSECTION` / `NEXT_SECTION`，未利用实体节点跨章节扩展
- [x] 跨文档推理：沿 `REFERENCES` 边追踪被引用规范，将其相关章节纳入上下文

**Reranker**
- [x] Reranker 统一应用：当前 `sequential` 策略未经过精排，导致结果质量低于 `parallel`
- [x] Reranker 内容截断优化：当前截断到 512 字符，改为按 token 截断，减少信息损失

**多跳推理**
- [x] 多跳推理迭代上限保护：当前 `multi_hop.py` 无最大迭代次数限制，存在死循环风险
- [x] 多跳中间步骤可见化：前端展示推理链路（子问题 → 召回章节 → 子答案）

---

### 数据质量与一致性

- [x] 同步端点补齐：`POST /api/query`（同步）缺少 `history` 和 `images` 参数，与流式端点不一致
- [x] Session vs Conversation 统一：存在 Neo4j `QuerySession` 与 PostgreSQL `Conversation` 两套历史存储，需合并或明确分工
- [x] Section 节点冗余字段清理：`section_number` 与 `number` 字段重复存储（`neo4j_writer.py:65-66`）
- [x] 图片分析结果缓存：重复入库相同图片时跳过 VLM 调用，避免浪费 API 额度

---

### 实体与文档 API

- [x] `GET /api/documents/{doc_id}/entities` — 列出文档中所有工具/材料/工序节点
- [x] `GET /api/entities?type=Tool&q=扳手` — 实体搜索与过滤
- [x] `GET /api/documents/{doc_id}/images` — 列出文档图片及 VLM 描述
- [x] `POST /api/documents/{doc_id}/reanalyze` — 对已入库文档重新提取实体/图片（用于模型升级后）
- [x] `GET /api/query/suggest?q=...` — 基于知识图谱的查询建议/自动补全

---

### 工程基础设施

- [x] 配置文件去重：`config.py` 中 `MILVUS_HOST`、`REDIS_URL`、`LLM_API_URL` 等存在重复定义，后者覆盖前者
- [x] PostgreSQL 索引补齐：`conversations` 表缺 `user_id` 索引，`query_feedback` 表无任何索引
- [x] Neo4j 全文索引验证：启动时检查 `cps_fulltext_index` 是否存在，不存在则自动创建
- [x] GPU 支持：Embedder 硬编码 `device="cpu"`，需检测 CUDA 并自动切换
- [x] 配置热重载：修改模型/策略配置后无需重启服务

---

### 前端与用户体验

- [x] 文档对比页差异算法：当前用字符串相等判断差异，改为 Myers diff 算法，支持词级高亮
- [x] 浅色 / 深色主题切换
- [x] 移动端适配
- [x] 知识图谱节点搜索框：在图谱页输入节点名称快速定位并高亮
- [x] 对话分支：支持从某条 AI 消息处新开分支，探索不同追问路径

---

### 测试覆盖

- [x] 实体提取单元测试（`entity_extractor.py` / `entity_writer.py`）
- [x] 检索策略集成测试（parallel / sequential / graph_augmented / multi_hop）
- [x] Reranker 效果回归测试（保证精排结果质量）
- [x] 多轮对话端到端测试
- [x] 流式 SSE 响应测试
- [x] 鉴权边界测试（未登录/无权限访问受保护接口）

---

## 企业级生产就绪清单

> 当前系统已完成 MVP 核心功能，以下为进入生产环境前需补齐的企业级能力。

### 安全加固

- [ ] **密钥与凭证管理**：当前 JWT_SECRET、数据库密码等均为 `.env` 明文，集成 HashiCorp Vault 或云端 Secrets Manager（AWS Secrets Manager / GCP Secret Manager），并在启动时强制校验非默认值
- [ ] **传输层加密**：docker-compose 中各服务间通信未启用 TLS；生产部署需为 Neo4j、PostgreSQL、Redis、Elasticsearch 配置 TLS 证书
- [ ] **Redis 认证**：当前 Redis 无密码，需启用 `requirepass` 并在连接串中配置
- [ ] **Elasticsearch 安全模式**：当前 `xpack.security.enabled=false`，生产需启用 xpack 鉴权与 TLS
- [ ] **文件上传防护**：`/api/ingest` 无文件大小上限与类型校验，需加 `max_size`（如 200MB）及 MIME 类型白名单（仅 PDF）
- [ ] **请求体大小限制**：FastAPI 全局配置 `max_request_body_size`，防止超大 JSON 攻击
- [ ] **依赖漏洞扫描**：集成 `pip-audit`（Python）+ `npm audit`（前端）定期扫描已知 CVE

---

### CI/CD 流水线

- [ ] **后端测试流水线**：GitHub Actions `test.yml`，在每个 PR 上自动运行 `pytest tests/ -v --cov`，覆盖率低于阈值时阻断合并
- [ ] **前端测试流水线**：GitHub Actions 运行 `vitest run` + `biome check`（lint/format），失败时阻断合并
- [ ] **Docker 镜像自动构建**：合并至 main 分支时自动构建并推送镜像至 Docker Registry（GHCR 或私有仓库）
- [ ] **安全扫描**：`security.yml` 中集成 Trivy（镜像漏洞扫描）+ `git-secrets`（防止密钥入库）
- [ ] **语义化版本与 Changelog**：集成 `semantic-release`，根据 commit message 自动生成版本号和 CHANGELOG.md
- [ ] **预提交钩子**：`.pre-commit-config.yaml`，统一 ruff + black（Python）及 biome（TypeScript）格式

---

### 可观测性与监控

- [ ] **请求关联 ID（Correlation ID）**：中间件为每个请求生成 UUID 并写入日志上下文，贯穿 Neo4j / PostgreSQL / LLM 全链路，便于生产问题追踪
- [ ] **OpenTelemetry 分布式追踪**：集成 `opentelemetry-sdk`，自动 instrument FastAPI / SQLAlchemy / httpx，导出至 Jaeger 或 Grafana Tempo
- [ ] **Prometheus 指标暴露**：集成 `starlette-prometheus`，暴露 `/metrics` 端点，包含 QPS、延迟分位数、缓存命中率、LLM token 消耗等指标
- [ ] **Grafana 仪表盘**：基于 Prometheus 指标搭建运营大盘（查询成功率、检索延迟 P50/P99、向量库 QPS、LLM 费用趋势）
- [ ] **告警规则**：配置 Alertmanager 规则，在服务宕机、错误率 > 5%、P99 延迟 > 5s 时触发告警（钉钉 / 企业微信 webhook）
- [x] **LLM 成本追踪**：在 Langfuse trace 中记录每次调用的 prompt/completion token 数及费用估算，支持按用户/部门分摊

---

### 高可用与容错

- [ ] **LLM API 重试与熔断**：使用 `tenacity` 对 LLM API 调用实现指数退避重试（最多 3 次），并用 `pybreaker` 实现熔断，防止级联失败
- [x] **向量库 / 图数据库连接池健康检查**：启动时及运行时定期 ping，连接失败时降级（仅全文检索）而非直接 500
- [ ] **异步任务队列**：将 PDF 入库（耗时 > 30s）迁移至 Celery + Redis 队列，支持任务重试、失败重新入队，前端通过 WebSocket 订阅进度（当前同步阻塞）
- [ ] **优雅关闭（Graceful Shutdown）**：捕获 SIGTERM，等待当前流式响应完成后再关闭，防止用户请求被截断
- [x] **数据库连接池调优**：PostgreSQL `pool_size` / `max_overflow` / `pool_timeout` 根据并发量配置，并添加慢查询日志（`echo_slow_threshold`）

---

### 多租户与访问控制

- [ ] **文档权限模型**：为 Document 表添加 `owner_id` + `visibility`（private / department / public），用户只能检索有权限的文档
- [ ] **对话隔离**：Conversation 查询时强制过滤 `user_id = current_user.id`，防止越权读取他人历史
- [ ] **部门级知识库隔离**：支持按部门（department）划分文档访问范围，管理员可配置跨部门共享
- [ ] **资源配额**：每用户每天查询次数上限（当前仅全局限流），存储配额（上传文档大小/数量），超限返回 429 并提示

---

### API 工程化

- [ ] **API 版本管理**：所有路由迁移至 `/api/v1/` 前缀，旧路径保留 6 个月并返回 `Deprecation` 响应头，为未来破坏性变更预留空间
- [ ] **分页一致性**：当前 `/api/documents` 用 `page/per_page`，其余接口用不同参数名；统一为 `cursor` 游标分页，支持大数据集无损翻页
- [ ] **幂等性保障**：`POST /api/ingest` 等写操作支持 `Idempotency-Key` 请求头，避免网络超时后客户端重试造成重复入库
- [ ] **OpenAPI 客户端生成**：发布 `openapi.json`，并在 CI 中自动生成 Python / TypeScript SDK 供内部系统集成

---

### 数据治理与合规

- [ ] **审计日志保留策略**：`AuditLog` 表当前无过期机制，添加定时任务（APScheduler）保留最近 1 年记录并归档至对象存储
- [ ] **数据导出与删除（Right to Erasure）**：`DELETE /api/users/me` 时级联删除对话、反馈、配置数据，满足数据合规要求
- [ ] **操作审计增强**：当前审计日志覆盖用户管理，需扩展至文档删除、实体合并、配置修改等敏感操作
- [ ] **查询日志脱敏**：日志中可能包含用户输入的敏感内容（如人名、工号），需在落盘前做正则脱敏

---

### 基础设施即代码（IaC）

- [ ] **Kubernetes 部署清单**：将 docker-compose.yml 转换为 Helm Chart（`charts/kg-rag/`），包含 Deployment / Service / PVC / ConfigMap / Secret 模板
- [ ] **多环境配置分离**：`docker-compose.dev.yml` / `docker-compose.staging.yml` / `docker-compose.prod.yml`，各环境独立的资源限制、副本数、镜像标签
- [ ] **自动扩缩容（HPA）**：Kubernetes HPA 基于 CPU / 自定义 QPS 指标自动扩展 FastAPI 副本（1-10 个）
- [ ] **备份与恢复**：PostgreSQL 每日自动备份至对象存储（`pg_dump` + S3/MinIO），Neo4j 增量备份脚本，定期演练恢复流程
- [ ] **灾难恢复演练文档**：记录 RTO（恢复时间目标）、RPO（恢复点目标），以及各服务故障时的降级策略

---

### 性能优化

- [ ] **Embedding 批处理**：当前每条 section 逐一调用 `encode()`，迁移至 `encode(batch)` 并发处理，入库速度预计提升 5-10×
- [ ] **向量索引离线构建**：大规模入库时暂停在线索引更新（Milvus `disable_index`），批量写入后重建，避免实时索引影响写入吞吐
- [ ] **Neo4j 查询缓存**：对高频只读 Cypher 查询（图谱统计、实体列表）添加应用层 Redis 缓存（TTL 5 分钟）
- [x] **前端资源优化**：D3.js 图谱渲染节点超 500 时启用 Canvas 模式替代 SVG，避免 DOM 膨胀导致浏览器卡顿
- [ ] **流式响应背压控制**：当前 SSE 无限速，LLM 生成过快时前端可能积压；添加服务端速率控制（字符/秒上限可配置）

---

### 用户体验完善

- [x] **浅色 / 深色主题切换**：`ThemeToggle` 组件切换 `.dark` class，偏好持久化至 localStorage
- [x] **查询历史搜索**：对话侧边栏支持按关键词过滤历史对话标题，避免对话过多时难以定位
- [x] **快捷键帮助面板**：`?` 键打开浮层展示所有全局快捷键（`⌘K` 搜索 / `⌘/` 问答 / `⌘B` 侧边栏等）
- [x] **消息引用回复**：点击来源章节 ↩ 触发引用，输入框上方高亮显示被引章节，提交时引用信息随问题一并发送
- [x] **PDF 在线预览**：文档详情页内嵌 iframe 查看器，支持水印覆盖、加载状态、下载，与章节目录并排显示
- [x] **离线状态提示**：网络断开时前端 SSE 流自动重连（指数退避，最多 3 次，延迟 1→2→4s），顶部 NetToast 提示连接状态

---

### 测试补强

- [ ] **负载测试**：使用 Locust 模拟 50 并发用户持续查询，验证 P99 延迟 < 3s，吞吐量 > 20 QPS
- [ ] **混沌工程**：模拟 Neo4j / Milvus 宕机时系统的降级行为（预期：返回全文检索结果而非 500）
- [ ] **前端 E2E 测试**：Playwright 覆盖登录 → 上传文档 → 提问 → 查看图谱的完整用户旅程
- [ ] **安全渗透测试**：OWASP ZAP 自动扫描 + 手工测试 SQL 注入、XSS、IDOR（越权读取他人对话）
- [ ] **LLM 评估基准**：构建 50 条 "问题-标准答案" 对，在每次模型/策略变更后自动计算 BLEU / ROUGE / 人工评分，防止效果回归

---

## 智能知识图谱演进路线图

> 当前图谱已实现：7 种节点类型 · 18 种关系类型 · 力导向可视化 · 图增强检索 · 多跳推理
> 以下为面向航空制造领域的深度图智能能力扩展规划，从数据建模到 AI 推理全面覆盖。

---

### 一、图谱结构扩展：更丰富的知识表示

**新节点类型**
- [ ] **Standard（标准规范节点）**：将 GJB、AS9100、HB、MIL-SPEC 等外部标准写入图谱，与 Document 建立 `COMPLIES_WITH` / `REFERENCED_BY` 关系，支持合规性追踪
- [ ] **Component（零件节点）**：从工艺规范中提取零件编号（如 P/N、件号），建立 `(Section)-[:APPLIES_TO]->(Component)` 关系，支持按零件查询所有相关工艺
- [ ] **Person / Role（人员角色节点）**：文档编制者、审核者、批准者，`(Document)-[:AUTHORED_BY]->(Person)`，支持追溯文档责任链
- [ ] **Equipment（设备/工装节点）**：区别于 Tool（手工工具），Equipment 指专用工装夹具、检测设备（如扭矩扳手校准仪），`(Section)-[:REQUIRES_EQUIPMENT]->(Equipment)`
- [ ] **Step（工序步骤节点）**：将 Section 中的有序步骤拆解为独立节点，`(Section)-[:HAS_STEP {order}]->(Step)-[:NEXT_STEP]->(Step)`，支持步骤级检索与重排
- [ ] **Hazard（危险源节点）**：从安全警告中提取危险源（如高压液压油喷射风险），`(Section)-[:WARNS_OF]->(Hazard)`，构建安全知识子图
- [ ] **Inspection（检验节点）**：提取质量检验要求，`(Section)-[:REQUIRES_INSPECTION]->(Inspection {method, frequency, acceptance_criteria})`
- [ ] **ChangeRecord（变更记录节点）**：每次文档版本更新时创建，存储变更原因、审批人、生效日期，`(Document)-[:HAS_CHANGE_RECORD]->(ChangeRecord)`

**新关系类型**
- [ ] **`PRECEDES` / `FOLLOWS`（工序先后）**：跨章节的工序依赖关系，如"液压测试必须在管路安装后进行"，支持工艺流程的拓扑排序
- [ ] **`CONFLICTS_WITH`（冲突检测）**：自动识别同一零件在不同文档中出现矛盾的工艺要求（如力矩值不一致），建立冲突边并告警
- [ ] **`DERIVED_FROM`（知识溯源）**：当某工艺节点由另一基础规范推导而来时，建立溯源关系，支持"为什么要这样做"的深层追问
- [ ] **`VALIDATED_BY`（验证关系）**：将工艺参数（Constraint）与试验报告或验证记录关联，`(Constraint)-[:VALIDATED_BY]->(Document {type: "test_report"})`
- [ ] **`SUPERSEDES_SECTION`（章节级版本替换）**：粒度比文档级 `SUPERSEDES` 更细，精确到哪个章节被哪个新章节替代

---

### 二、图算法与智能分析

**图拓扑分析**
- [ ] **PageRank 重要性排序**：对 Section 节点运行 PageRank（被引用次数多的章节权重高），检索时将 PageRank 分数融入 RRF 排名，提升核心工艺章节的召回优先级
- [ ] **社区检测（Louvain / LPA）**：使用 Neo4j GDS 对节点进行社区发现，识别高度相关的工艺簇（如"液压系统相关章节集合"），用于自动生成工艺主题标签
- [ ] **中心性分析（Betweenness Centrality）**：找出图谱中的"桥接节点"（连接不同工艺领域的关键章节），高中心性节点可能是跨专业知识的核心交汇点
- [ ] **最短路径查询**：`GET /api/graph/path?from=doc_id_A&to=doc_id_B` 返回两文档/章节之间的知识关联路径，解释为什么两份规范相互关联
- [ ] **子图相似度**：当导入新文档时，自动计算与已有文档的子图结构相似度（GED / WL kernel），识别重复或高度相似的工艺规范
- [ ] **知识覆盖度热力图**：对图谱进行密度分析，识别哪些零件类型、工艺领域的知识节点稀疏（知识盲区），输出覆盖度报告

**推理与问题检测**
- [ ] **约束冲突检测引擎**：自动比对同一 Component 上来自不同 Document 的 Constraint 节点，若力矩范围、温度限值有交叉矛盾则生成告警，`POST /api/graph/conflict-check?component=`
- [ ] **工艺完整性校验**：检测工序图中的孤立节点（有 Section 但无 Tool / Material / Process 关联），生成"实体提取不完整"报告，辅助数据质量改进
- [ ] **悬空引用检测**：扫描所有 `REFERENCES` 边，若目标文档不在图谱中则标记为悬空引用，提示管理员补充入库
- [ ] **循环依赖检测**：检测工序先后关系（`PRECEDES`）中是否存在环路（A→B→C→A），防止工艺流程逻辑错误
- [ ] **版本一致性检查**：检测同一设备型号下，不同版本文档之间 Constraint 值的漂移趋势，自动生成版本对比报告

---

### 三、图增强检索：从语义到结构的融合

**检索策略升级**
- [x] **图神经网络（GNN）检索**：训练 GraphSAGE 模型，将节点结构特征（邻居类型分布、关系密度）融入节点 Embedding，替代纯文本向量，提升结构相似节点的检索精度
- [ ] **个性化 PageRank（PPR）检索**：以用户查询锚定的初始节点为种子，运行个性化 PageRank，按随机游走概率排序候选节点，替代当前固定深度的 BFS 扩展
- [ ] **关系路径感知检索**：将"两节点之间通过哪种路径连接"作为语义特征，区分"直接相关"（共享 Tool）与"间接相关"（共享 Material 再共享 Process），差异化加权
- [ ] **时序感知检索**：查询时默认优先返回最新版本文档的章节，过期章节降权（基于 `SUPERSEDES` 关系链的版本时序）
- [ ] **对比检索模式**：`strategy=compare` 新策略，自动并行检索两份文档的相同主题章节，输出结构化对比结果（差异项、共同点、冲突点）
- [ ] **约束感知检索**：检测问题中是否含数值（如"液压压力 3000 PSI"），若有则优先召回 Constraint.value 范围覆盖该数值的章节

**上下文图构建**
- [ ] **动态子图提取**：回答问题时不仅返回相关 Section，同时提取以这些节点为中心的 2 跳子图（包含 Tool、Material、Constraint），将子图结构序列化为 LLM 上下文的结构化补充
- [ ] **推理链图谱化**：将多跳推理过程（子问题→节点→边→子答案）以图结构记录并存入 Neo4j，支持后续查询"这个答案是如何推理得出的"
- [x] **反事实图查询**：支持"如果去掉 X 工序，Y 零件还能满足 Z 要求吗？"类型的假设推理，通过图谱中的约束路径模拟因果链

---

### 四、时序与版本智能

- [x] **版本时间线视图**：前端新增 Timeline 视图，以横轴为时间、纵轴为文档，展示版本演进、章节变更、关系新增的历史序列
- [ ] **章节级 Diff 图谱**：对同一章节的两个版本，生成 Myers Diff 并将变更写入图谱（`CHANGED_TO` 边携带 diff patch 属性），支持"这个章节改了什么"的精确问答
- [ ] **变更影响分析**：当一个 Document 更新版本时，自动沿 `REFERENCES` 关系扩散，找出所有引用该文档的下游规范，生成"受影响文档清单"，辅助变更管理
- [ ] **变更频率热力图**：统计各 Section 节点的历史变更次数（`ChangeRecord` 节点数量），在图谱上以热力色渲染，识别"高度易变"章节（可能存在工艺不成熟问题）
- [ ] **有效性时间窗口**：为 Document / Section 节点增加 `valid_from` / `valid_until` 属性，查询时自动过滤生效期外的节点（支持"查询某时间点有效的工艺规范"）
- [ ] **废止预警**：定期扫描 `OBSOLETED_BY` 关系，若系统内存在指向已废止文档的 `REFERENCES` 边，则触发告警通知文档管理员

---

### 五、领域本体与外部知识融合

- [ ] **航空领域本体对齐**：导入 ATA 100 章节码（飞机系统分类标准）作为顶层分类本体，将 Document / Section 节点映射至对应 ATA Chapter，支持按 ATA 章节号检索（如"ATA 29 液压系统所有相关规范"）
- [ ] **合规性矩阵**：构建规范 → 标准条款的映射图（如 GJB 241 §3.2.1 → 本系统某工艺章节），`GET /api/graph/compliance-matrix?standard=GJB241` 输出覆盖度矩阵，识别合规盲区
- [ ] **术语本体（Ontology）**：建立航空制造术语同义词表，统一"液压泵"/"液压驱动泵"/"液压系统泵"等变体，作为图谱实体归一化的权威词典
- [ ] **供应商知识图谱**：将材料供应商信息（`Supplier` 节点）接入，`(Material)-[:SUPPLIED_BY]->(Supplier {approval_status, lead_time})`，支持"这个材料有哪些合格供应商"
- [ ] **BOM（物料清单）集成**：从 ERP/PDM 系统导入 BOM 数据，将零件号（Part Number）节点与图谱中的 Component 节点对齐，实现工艺规范与制造清单的双向追溯
- [ ] **CAD 元数据关联**：从 STEP/IGES 文件中提取几何特征（材料、公差带、表面粗糙度），与图谱中的 Constraint 节点匹配，打通设计-工艺-制造数据孤岛

---

### 六、可视化与交互升级

**多视图模式**
- [ ] **层级树状图（Hierarchy View）**：Document → Section → Subsection 的树形折叠展开，适合快速浏览单个规范的章节结构，与力导向图互相切换
- [ ] **关系矩阵视图（Adjacency Matrix）**：行列均为 Document 节点，格子颜色编码 `REFERENCES` / `SIMILAR_TO` 关系强度，适合发现文档间的高频引用簇
- [ ] **桑基图（Sankey Diagram）**：展示从工艺流程（Process）→ 使用的工具（Tool）→ 消耗的材料（Material）→ 产生的约束（Constraint）的能量流向，直观呈现工艺链路
- [x] **时间线图（Timeline View）**：以版本号为 X 轴，文档为 Y 轴，节点变更事件为气泡，动态播放知识库演进历史
- [ ] **地理热力图**：若文档与工厂车间（Shop）关联，在厂区平面图上叠加工艺规范热力（哪个工位涉及最多规范），支持数字化车间场景

**交互能力**
- [ ] **图上直接编辑**：管理员在可视化界面中拖拽创建关系（如将两个 Tool 节点连上 `ALTERNATIVE_TO` 边），无需写 Cypher，操作自动同步至 Neo4j
- [ ] **Cypher 查询控制台**：专家用户可直接输入 Cypher 查询语句，结果实时渲染为交互图谱，支持图谱探索性分析
- [ ] **节点注释与标注**：用户可对任意节点添加注释（`Note` 节点），`(Section)-[:HAS_NOTE {author, created_at}]->(Note)`，团队协作标注知识盲点或疑问
- [x] **图谱快照与分享**：将当前图谱视图（含过滤、高亮状态）保存为 URL 可分享的快照，团队成员打开链接可复现完全相同的视图状态
- [ ] **增量渲染与虚拟化**：节点超过 1000 时切换为 WebGL（Three.js / PixiJS）渲染，维持交互帧率 > 30fps；超过 5000 时降级为 Canvas 静态热力图
- [x] **图谱漫游模式（Graph Tour）**：以某主题（如"液压系统安装"）为起点，AI 自动规划一条穿越相关节点的导览路径，逐步展开讲解每个节点的知识要点

---

### 七、图谱驱动的 AI 能力

**问答与推理**
- [ ] **图谱原生问答（KGQA）**：将用户自然语言问题翻译为 Cypher 查询（Text2Cypher），直接从图谱结构中精确提取答案（如"GJB 241 中涉及的所有力矩约束值"），补充向量检索的精确性不足
- [ ] **反向追问（Backward Chaining）**：给定一个结论（如某零件裂纹），沿因果关系链反向推导可能的根因工艺问题（Material 不合规 / Constraint 未满足 / Tool 磨损）
- [ ] **工艺路线规划**：给定零件和目标状态，图谱自动推导最优工艺路线（拓扑排序 + 约束满足），输出有序的工序步骤清单
- [ ] **知识图谱问题生成**：基于图谱结构自动生成考核题目（如"根据 CPS1220 §3.2，安装液压接头时应使用哪种扭矩工具？"），用于工艺培训考核
- [ ] **异常工艺诊断**：描述一个工艺异常现象，图谱检索相关 Hazard / Constraint / Inspection 节点，LLM 结合图结构推断违规的工艺步骤和改正建议

**自动化与持续学习**
- [ ] **图谱自动补全**：检测孤立 Section 节点（无 Tool/Material/Process 关联），批量提交 LLM 重新提取实体，实现图谱的自愈式数据填充
- [ ] **关系预测（Link Prediction）**：训练 TransE / RotatE 等知识图谱嵌入模型，预测可能缺失的关系（如某 Section 可能还 `REQUIRES_TOOL` 某 Tool，但提取时遗漏），置信度高于阈值时推荐给管理员确认
- [ ] **实体对齐（Entity Alignment）**：当导入来自不同供应商的规范时，自动识别不同文档中指称相同实体的节点（如"HB/T 5292" 与 "HB5292" 指同一标准），消除同义异名冗余
- [ ] **图谱嵌入持久化**：定期（每周）将所有节点的图结构 Embedding（Node2Vec / GraphSAGE）写入 Milvus，支持"结构相似节点检索"（超越纯文本相似度）
- [ ] **主动学习标注**：系统识别图谱中置信度低的边（如 `SIMILAR_TO` 分数在 0.8-0.9 之间的模糊关系），主动推送给领域专家确认或拒绝，持续提升图谱质量

---

### 八、协作与知识管理

- [ ] **专家知识录入界面**：领域专家通过结构化表单（非自由文本）直接向图谱录入工艺知识条目（Tool / Process / Constraint），系统自动生成对应节点和关系，降低知识入库门槛
- [ ] **图谱评审工作流**：新提取的节点/关系默认为 `draft` 状态，须经过至少一名领域专家审核（`APPROVED_BY`）后才进入正式检索，建立知识质量闸门
- [ ] **知识订阅与推送**：用户可订阅特定 Document 或 Component 的图谱变更（如文档更新版本），订阅事件触发站内消息或邮件通知
- [ ] **知识贡献排行**：统计每位用户审核通过的节点数、修正的实体合并数，形成知识贡献积分，激励专家参与图谱维护
- [ ] **问题挂载到图谱**：用户提问后，将问题节点（`Query`）与回答涉及的 Section 节点挂载，`(Query)-[:ANSWERED_BY]->(Section)`，形成"常见问题图谱"，高频问题对应的章节自动提升权重

---

### 九、运营与监控

**图谱健康度**
- [ ] **图谱健康度仪表盘**：专属管理页面实时展示六项核心指标：孤立节点数（无任何关系的节点）、悬空引用数（`REFERENCES` 目标不在库中的比例）、Constraint 覆盖率（有约束节点的 Section 占比）、实体提取待处理队列长度、近 7 天新增节点/关系趋势折线图；综合健康分低于阈值时页面顶部 Banner 警示，`GET /api/admin/graph/health`
- [ ] **悬空引用扫描**：`POST /api/admin/graph/scan-dangling` 扫描全库 `REFERENCES` 关系，列出目标文档不在库中的清单，结果写入 `SystemSetting`，每日定时自动触发；管理界面展示"待补充入库文档 Top 10"，一键跳转至批量导入页
- [ ] **实体覆盖率报告**：对每份文档统计有 Tool / Material / Process 关联的 Section 占比，覆盖率低于 30% 的文档标记为"实体提取不完整"，`GET /api/admin/documents/coverage-report` 返回文档级覆盖度排行，支持批量触发 `/reanalyze` 补跑
- [ ] **图谱一致性校验**：定期脚本检查：① Section 有 `doc_id` 但找不到父 Document；② Constraint 有 `chunk_id` 但关联 Section 已删除；③ `NEXT_SECTION` 关系是否形成环路；④ 图片节点 `path` 指向的文件是否仍然存在；发现异常写入 `audit_logs`，并在健康度仪表盘高亮显示

**变更管理**
- [ ] **图谱变更日志**：记录每次节点创建/修改/删除、关系新增/删除的操作日志（`operator`, `timestamp`, `operation_type`, `entity_type`, `entity_id`, `before`, `after`），存入 PostgreSQL `graph_changelog` 表；`GET /api/admin/graph/changelog?since=&type=&operator=` 支持多维过滤，`GET /api/admin/graph/changelog/{id}` 查看变更前后快照对比
- [ ] **变更回滚**：`POST /api/admin/graph/changelog/{id}/rollback` 执行单条变更的反向操作（删除→重建、属性修改→还原旧值、关系删除→重建），支持按时间段批量回滚同一操作集，回滚前要求管理员二次确认
- [ ] **增量同步 API**：`GET /api/graph/changelog?since=2026-01-01&format=ndjson` 返回指定时间后的图谱变更列表（JSON Patch 格式，含节点属性 diff），支持 ETag 增量拉取；供下游系统（ERP / MES / PLM）定时订阅，实现工艺知识库与制造执行系统的双向同步
- [ ] **图谱备份与时间点恢复**：APScheduler 定时任务（每日凌晨 2:00）触发 `neo4j-admin dump` 快照，压缩归档至对象存储（MinIO / S3），保留最近 30 天；`POST /api/admin/graph/restore?snapshot_id=` 支持回滚至任意历史快照，恢复前自动创建当前状态备份，满足等保三级审计留痕要求

**查询运营分析**
- [ ] **查询热力分析**：统计哪些 Section 节点作为检索来源被引用最频繁（基于 `query_feedback` 的 `clicked_source` 事件 + 流式返回的 sources 列表），`GET /api/admin/analytics/hot-nodes?top_k=20&days=30` 输出热点节点排行，热力值反映在可视化图谱的节点大小/亮度上，指导图谱扩充优先级
- [ ] **检索策略效果对比**：按策略（parallel / graph_augmented / multi_hop / sequential）分组统计平均端到端延迟、👍 好评率、平均返回来源数量、LLM token 消耗，`GET /api/admin/analytics/strategy-stats?days=30`；结果表格辅助调整"自动策略选择"的路由规则
- [ ] **零结果查询监控**：记录 `sources` 为空的查询词，`GET /api/admin/analytics/empty-queries?days=7` 输出高频零结果词表（知识盲区），每周自动邮件推送至文档管理员，指导下一批 PDF 优先入库范围
- [ ] **用户活跃度报表**：按用户 / 部门统计 DAU、周查询量、平均会话轮数、最常用检索策略，`GET /api/admin/analytics/user-activity?days=30`；支持导出 CSV，对接企业 BI 工具（如 Metabase / Superset）

**成本与资源监控**
- [x] **LLM 成本追踪**：每次 LLM 调用将 prompt / completion token 数和费用估算（USD / CNY）写入 `llm_usage` 表，`GET /api/admin/llm-costs?days=30&group_by=user|department|model|day` 多维度费用分摊报表；Langfuse generation 同步推送完整用量元数据，支持可观测性仪表盘实时查看
- [ ] **Token 预算告警**：`SystemSetting` 中存储 `budget_usd_{department}` 各部门月度预算，消耗超过 80% 时推送预警（邮件 / 钉钉），超过 100% 时自动降级至预设的低价备用模型，防止超支；`GET /api/admin/llm-costs/budget-status` 返回各部门预算消耗进度
- [ ] **存储容量监控**：定期统计 Neo4j 节点/关系总量、Milvus 向量条数与磁盘占用、PostgreSQL 各表大小、`uploads/` 目录 PDF 文件总大小，`GET /api/admin/storage/stats`；容量超过水位线（80%）时触发告警，并输出各文档占用空间 Top 10 辅助清理决策
- [ ] **Prometheus + Grafana 运营大盘**：集成 `starlette-prometheus` 暴露 `/metrics` 端点，导出 QPS、P50/P99 检索延迟、缓存命中率、Neo4j / Milvus 连接池状态、LLM token 消耗趋势等指标；Grafana 大盘分"实时监控"与"运营周报"两个视角；Alertmanager 配置在错误率 > 5%、P99 > 5s、服务宕机时触发告警

**告警与通知**
- [ ] **多通道告警路由**：支持钉钉群机器人、企业微信 Webhook、邮件三种告警通道，`SystemSetting` 中存储各通道配置；按告警级别路由——INFO 写日志、WARN 推企业微信、CRITICAL 推钉钉并抄送邮件；`POST /api/admin/alerts/test` 发送测试告警验证配置有效性
- [ ] **告警聚合与静默**：同类告警 10 分钟内合并为一条推送，避免告警风暴；`POST /api/admin/alerts/silence` 支持在维护窗口期间临时屏蔽指定告警规则（含过期自动恢复）；所有告警事件持久化至 `audit_logs`，支持告警历史回溯
- [ ] **SLA 可用性统计**：以分钟为粒度记录 `/api/query` 和 `/api/query/stream` 的成功率，滚动计算 30 天 SLA（目标 99.9% = 月均故障 < 43 分钟）；`GET /api/admin/sla` 返回每日可用性热力日历和月度 SLA 达标情况，供服务协议履约核查

---

### 十、垂直领域深化（航空制造专项）

- [ ] **适航符合性映射**：将工艺规范与适航条款（CCAR-25、FAR-25、CS-25）建立对应关系，支持适航审查时快速定位相关工艺依据
- [ ] **工艺 FMEA 图谱化**：将失效模式与影响分析（FMEA）结构化录入：`(Process)-[:HAS_FAILURE_MODE]->(FailureMode {severity, occurrence, detection, RPN})`，支持按 RPN 值排序高风险工序
- [ ] **特种工艺追踪**：为焊接、热处理、表面处理、无损检测等特种工艺建立专属节点类型，关联认证要求（操作者资质、设备鉴定周期）
- [ ] **首件鉴定关联**：将首件鉴定报告（FAI）与相关工艺章节挂钩，`(Document {type:"FAI"})-[:VALIDATES]->(Section)`，支持"这个工序的首件鉴定状态"查询
- [ ] **工程更改单（ECO）图谱**：将 ECO 作为图谱中的一等公民节点，连接变更前/后的 Section 节点和受影响的 Component 节点，实现工程变更的全链路追踪
