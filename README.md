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
- [x] **对话隔离**：Conversation 查询时强制过滤 `user_id = current_user.id`，防止越权读取他人历史
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
- [x] **增量渲染与虚拟化**：节点超过 1000 时切换为 WebGL（Three.js / PixiJS）渲染，维持交互帧率 > 30fps；超过 5000 时降级为 Canvas 静态热力图
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
- [x] **查询热力分析**：统计哪些 Section 节点作为检索来源被引用最频繁（基于 `query_feedback` 的 `clicked_source` 事件 + 流式返回的 sources 列表），`GET /api/admin/analytics/hot-nodes?top_k=20&days=30` 输出热点节点排行，热力值反映在可视化图谱的节点大小/亮度上，指导图谱扩充优先级
- [x] **检索策略效果对比**：按策略（parallel / graph_augmented / multi_hop / sequential）分组统计平均端到端延迟、👍 好评率、平均返回来源数量、LLM token 消耗，`GET /api/admin/analytics/strategy-stats?days=30`；结果表格辅助调整"自动策略选择"的路由规则
- [x] **零结果查询监控**：记录 `sources` 为空的查询词，`GET /api/admin/analytics/empty-queries?days=7` 输出高频零结果词表（知识盲区），每周自动邮件推送至文档管理员，指导下一批 PDF 优先入库范围
- [x] **用户活跃度报表**：按用户 / 部门统计 DAU、周查询量、平均会话轮数、最常用检索策略，`GET /api/admin/analytics/user-activity?days=30`；支持导出 CSV，对接企业 BI 工具（如 Metabase / Superset）

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

---

## AI 生态扩展规划

> 以下技术栈可将本系统从"单体 RAG 应用"升级为"AI 生态节点"——既能被外部 AI 工具调用，也能主动编排多个 AI 能力协同完成复杂任务。

---

### 一、MCP（Model Context Protocol）— 让 AI 工具直接调用知识库

MCP 是 Anthropic 开源的标准协议，允许 Claude Desktop、Cursor、Zed 等支持 MCP 的客户端以工具调用方式直接访问外部数据源。将本系统暴露为 MCP Server 后，用户无需打开浏览器，即可在 AI 编辑器内直接查询航空工艺规范。

**可暴露的 MCP Tools**

| Tool 名称 | 对应后端端点 | 功能描述 |
|-----------|------------|---------|
| `query_knowledge_base` | `POST /api/query/stream` | 自然语言问答，返回答案与来源章节 |
| `search_documents` | `GET /api/documents?q=` | 按关键词搜索文档列表 |
| `get_section_content` | `GET /api/documents/{doc_id}/sections` | 获取指定章节全文 |
| `get_entity_graph` | `GET /api/graph/data` | 获取知识图谱子图（节点 + 关系） |
| `search_entities` | `GET /api/entities?type=&q=` | 按类型/名称检索实体节点 |
| `compare_documents` | `GET /api/compare` | 对比两份规范的章节差异 |
| `get_graph_path` | `GET /api/graph/path` | 查询两节点间的知识关联路径 |

**实施方案**

- [ ] 新增 `mcp_server/` 目录，使用 `mcp` Python SDK（`pip install mcp`）实现 `StdioServer`
- [ ] 每个 Tool 对应一个 `@server.tool()` 装饰函数，内部调用现有 FastAPI 服务
- [ ] 发布 `claude_desktop_config.json` 示例，用户一键配置即可在 Claude Desktop 中使用
- [ ] 支持 SSE 传输模式（`mcp[sse]`），允许 Web 端 MCP 客户端流式接收问答结果
- [ ] MCP Resources 扩展：将文档列表暴露为 `resource://documents/{doc_id}`，AI 可直接"阅读"原始规范文本

---

### 二、Agent Skills — 领域专用工具集

将系统能力封装为结构化 Tool（Function Calling），供 LLM Agent 在多步推理中按需调用，而非依赖单次检索。

**核心 Skills 设计**

```python
# 工具定义示例（OpenAI Function Calling / Anthropic Tool Use 格式通用）
tools = [
    {
        "name": "query_procedure",
        "description": "查询特定工艺步骤的详细要求和约束条件",
        "parameters": {
            "procedure_name": "str — 工艺名称，如'液压管路安装'",
            "aspect": "str — 关注维度：steps / tools / materials / constraints / safety"
        }
    },
    {
        "name": "check_compliance",
        "description": "检查某工艺参数是否满足规范约束（如力矩值是否在允许范围内）",
        "parameters": {
            "parameter": "str — 参数名称",
            "value": "number — 实际值",
            "unit": "str — 单位"
        }
    },
    {
        "name": "find_related_specs",
        "description": "沿图谱 REFERENCES 关系查找与某规范相关联的上下游文档",
        "parameters": {
            "doc_id": "str — 文档编号",
            "direction": "str — upstream / downstream / both"
        }
    },
    {
        "name": "trace_change_history",
        "description": "查询某章节的历史版本变更记录",
        "parameters": {
            "doc_id": "str",
            "section_number": "str"
        }
    }
]
```

**实施方案**

- [ ] 在 `backend/src/skills/` 下实现各 Skill 的业务逻辑，独立于 RAG 检索管线
- [ ] 在 `multi_hop.py` 中将 LangGraph Agent 的工具列表升级为 Skills 集，替代硬编码子问题拆解
- [ ] 前端"策略"下拉新增 `agent` 选项，调用 `POST /api/query/agent`，后端以 ReAct 循环执行 Tool 调用直到得出最终答案
- [ ] 工具调用日志写入 Langfuse span，可视化每次推理的 Tool 调用链路和中间结果

---

### 三、A2A（Agent-to-Agent Protocol）— 多智能体协同

Google 开源的 A2A 协议定义了不同 AI Agent 之间互相发现、委托任务、交换上下文的标准接口。本系统可作为"工艺知识 Agent"节点，被外部 Agent（如设计验证 Agent、供应链 Agent）主动调用。

**集成场景**

- [ ] **对外暴露 Agent Card**：在 `/.well-known/agent.json` 发布标准 Agent Card，描述本系统的能力边界（支持的任务类型、输入输出格式、认证方式）
- [ ] **接收任务委托**：实现 `POST /api/a2a/tasks/send` 端点，接收其他 Agent 以 A2A 格式委托的问答或图谱查询任务，返回结构化结果
- [ ] **主动委托子任务**：当本系统判断问题超出工艺规范范围（如涉及 ERP 库存数据），通过 A2A 协议将子任务委托给企业内网的 ERP Query Agent
- [ ] **流式任务状态**：支持 A2A 的 `tasks/sendSubscribe` 流式端点，让调用方实时获取推理进度（类似当前的 SSE）

---

### 四、DSPy — 提示词自动优化

DSPy（Declarative Self-improving Python）将提示词工程转化为可编程、可优化的模块，通过少量标注样本自动搜索最优 Prompt 和 Few-shot 示例。

**适用场景**

- [ ] **实体提取优化**：当前 `entity_extractor.py` 依赖手写 Prompt；用 DSPy `ChainOfThought` 模块 + 50 条标注样本自动优化提取准确率
- [ ] **Reranker 分数校准**：以 `(query, chunk, relevance_label)` 三元组训练 DSPy 评分模块，替代固定阈值的硬截断逻辑
- [ ] **Text2Cypher 生成**：训练 DSPy 模块将自然语言问题翻译为 Cypher 查询，自动优化生成准确率（基于图谱执行结果的自动反馈）
- [ ] **答案质量评估**：DSPy `Assess` 模块自动评估 LLM 答案的忠实度（Faithfulness）和相关性（Relevance），替代人工抽检

**实施方案**

```bash
pip install dspy-ai
```
- [ ] `scripts/dspy_optimize_entity.py` — 实体提取 Prompt 优化脚本，输出最优 Prompt 写入 `config/prompts/entity.json`
- [ ] `scripts/dspy_optimize_cypher.py` — Text2Cypher 优化，基于图谱执行成功率自动反馈

---

### 五、Prompt Caching — 大幅降低 LLM 成本

Anthropic Claude API 支持 Prompt Caching，对超过 1024 token 的系统提示或文档内容进行服务端缓存，重复调用时 token 费用降低约 90%。

**适用场景**

- [ ] **系统提示缓存**：当前每次查询都重复发送约 800 token 的系统提示（角色定义 + 输出格式要求），启用 `cache_control: {"type": "ephemeral"}` 后缓存命中时费用接近零
- [ ] **长文档上下文缓存**：当同一章节被多次不同问题引用时，缓存该章节的 token 表示，避免重复编码（适用于热点章节）
- [ ] **Few-shot 示例缓存**：将固定的 few-shot 示例（实体提取、答案格式）写入缓存前缀，所有请求共享缓存
- [ ] **费用追踪区分**：在 `llm_usage` 表新增 `cache_read_tokens` / `cache_write_tokens` 字段，在成本报表中单独展示缓存节省金额

---

### 六、RAG 评估框架（RAGAS / TruLens）

自动化评估检索质量和答案质量，建立持续监控的效果基线。

**RAGAS 指标体系**

| 指标 | 含义 | 目标值 |
|------|------|--------|
| Faithfulness | 答案是否忠实于检索内容，无幻觉 | > 0.85 |
| Answer Relevancy | 答案是否切题 | > 0.80 |
| Context Recall | 检索结果是否覆盖了标准答案所需信息 | > 0.75 |
| Context Precision | 检索结果中有多少是真正相关的 | > 0.70 |

**实施方案**

- [ ] `scripts/ragas_eval.py` — 加载 50 条人工标注 QA 对，调用各检索策略，计算 RAGAS 四项指标并写入 `eval_results.json`
- [ ] GitHub Actions `eval.yml` — 每次合并至 main 时自动运行评估，若任一指标低于基线则在 PR 评论中告警
- [ ] 管理后台新增"评估报告"页，展示各策略（parallel / gnn / multi_hop）的 RAGAS 指标历史趋势折线图
- [ ] TruLens 集成：对每次生产查询进行在线评分（Groundedness + Answer Relevance），写入 PostgreSQL，异常低分查询自动加入人工复核队列

---

### 七、语义缓存（GPTCache / Redis Vector）

对语义相似的重复问题命中缓存，避免重复检索和 LLM 推理，降低延迟和成本。

**工作原理**

```
用户提问 → BGE-M3 编码为向量
         → 在 Redis / Milvus 中检索最相似的历史问题（余弦相似度 > 0.95）
         → 命中：直接返回缓存答案（< 50ms）
         → 未命中：走完整 RAG 管线，结果写入缓存
```

**实施方案**

- [ ] 集成 `gptcache` 库（`pip install gptcache`）或基于现有 Milvus 自行实现向量缓存层
- [ ] 相似度阈值可在管理后台配置（默认 0.95，过低导致错误命中，过高缓存命中率低）
- [ ] 缓存 TTL 默认 24 小时，文档更新时按 `doc_id` 批量失效相关缓存条目
- [ ] 命中统计写入 `cache_hits` 表，在成本报表中显示缓存节省的 token 数和费用

---

### 八、知识蒸馏与微调管线

利用系统积累的高质量问答数据，持续微调领域专用小模型，降低推理成本。

**数据飞轮**

```
用户查询 + 👍 反馈
    → 高质量 QA 对（question, context, answer）
    → 领域微调数据集
    → 微调 Qwen-7B / GLM-4-9B 等开源模型
    → 部署为本地 Ollama / vLLM 推理服务
    → 替代远程 API，延迟降低 60%，成本接近零
```

**实施方案**

- [ ] `scripts/export_finetune_data.py` — 从 `query_feedback`（rating=1）导出 SFT 格式数据集（Alpaca / ShareGPT 格式）
- [ ] `scripts/finetune_qwen.py` — 使用 LLaMA-Factory 或 Axolotl 对 Qwen2.5-7B 进行 LoRA 微调，训练数据为本系统积累的航空工艺问答对
- [ ] 微调后模型通过 Ollama 本地部署，在 `.env` 中切换 `LLM_MODEL` 即可无缝对接（系统已支持 OpenAI 兼容 API）
- [ ] A/B 测试框架：50% 流量走微调本地模型，50% 走原始 API，对比 RAGAS 指标和用户评分，验证蒸馏效果
- [ ] Reranker 微调：以 `(query, positive_chunk, negative_chunk)` 三元组微调 `bge-reranker-v2-m3`，提升航空术语的精排准确率

---

### 九、技术栈汇总（AI 生态）

| 类别 | 技术 | 作用 | 状态 |
|------|------|------|------|
| AI 协议 | MCP（Model Context Protocol） | 将知识库暴露为 AI 工具，供 Claude Desktop / Cursor 直接调用 | 规划中 |
| AI 协议 | A2A（Agent-to-Agent） | 与企业内网其他 AI Agent 互联互调 | 规划中 |
| Agent 框架 | LangGraph | 多跳推理 ReAct Agent，Tool Use 编排 | ✅ 已实现 |
| Agent 框架 | Agent Skills / Function Calling | 领域专用结构化工具集 | 规划中 |
| 提示优化 | DSPy | 自动优化实体提取、Text2Cypher、答案生成的 Prompt | 规划中 |
| 成本优化 | Anthropic Prompt Caching | 系统提示和热点文档缓存，成本降低 ~90% | 规划中 |
| 效果评估 | RAGAS | 自动评估 Faithfulness / Relevancy / Recall / Precision | 规划中 |
| 效果评估 | TruLens | 生产环境在线评分，异常问题自动入复核队列 | 规划中 |
| 响应加速 | 语义缓存（GPTCache） | 相似问题向量匹配命中缓存，< 50ms 响应 | 规划中 |
| 模型优化 | 知识蒸馏 + LoRA 微调 | 本地小模型替代远程 API，延迟和成本双降 | 规划中 |
| 图神经网络 | GraphSAGE GNN | 结构感知节点 Embedding，提升图结构相关章节召回 | ✅ 已实现 |
| 假设推理 | 反事实因果推理 | "如果去掉 X 步骤"类假设问题的图谱因果链模拟 | ✅ 已实现 |
| 可观测性 | Langfuse | LLM 调用链路追踪、Token 成本统计 | ✅ 已实现 |

---

## 企业级智能制造技术扩展

> 本章面向航空制造企业的纵深落地场景，从 RAG 技术演进、工业互联、MLOps、实时流处理、多模态感知、安全合规等维度，规划系统从"知识库问答"向"制造智能中枢"的升级路径。

---

### 十、先进 RAG 策略演进

当前系统已实现 Parallel / Sequential / Graph-Augmented / Multi-hop / GNN / Counterfactual 六种策略，以下为下一代检索增强技术方向。

**HyDE（假设文档嵌入）**

```
用户问题 → LLM 生成"假设性答案段落"（不依赖真实文档）
         → 对假设答案编码为向量
         → 以假设答案向量替代问题向量进行相似度检索
         → 可显著提升专业术语稀疏问题的召回率
```

- [ ] 在 `parallel.py` 中添加 `hyde=True` 开关，生成假设文档后与原始问题向量做加权平均再检索
- [ ] A/B 测试：对"定义型"问题（如"CPS1220 的技术要求"）HyDE 与标准向量的 Context Recall 对比

**Self-RAG（自省式检索）**

模型在生成过程中主动判断是否需要检索、检索结果是否相关、最终答案是否有依据，输出带有 `[Retrieve]` / `[Relevant]` / `[Supported]` 特殊 token 的受控生成。

- [ ] 微调一个 Self-RAG 判别头（基于 Qwen2.5-7B），或以 Prompt 模拟四种反射 token 的语义
- [ ] 在 `stream.py` 中实现"生成→判断→按需检索→继续生成"的迭代循环
- [ ] 当模型判定检索内容不支持时，自动触发二次检索（扩大 top-k 或切换策略），记录回退次数至 Langfuse

**CRAG（纠错式 RAG）**

对检索结果进行质量评分，低质量时降级为网络搜索或跨库检索，确保上下文质量底线。

- [ ] 训练轻量级相关性评估器（cross-encoder）：若 top-1 相关性分数 < 0.4，触发 fallback
- [ ] Fallback 策略链：① 扩大 top-k → ② 切换全文检索 → ③ 调用外部 Bing/Tavily API 搜索公开航空标准
- [ ] 评估器分数写入每条 source 的 `relevance_score` 字段，前端来源卡片展示可信度条

**Adaptive RAG（自适应路由）**

基于问题分类器自动选择最优检索策略，替代用户手动切换策略下拉框。

- [ ] 训练五分类 Prompt（或微调小模型）：`factual` / `procedural` / `comparative` / `constraint` / `hypothetical`
- [ ] 路由规则：factual → parallel，procedural → sequential + graph，comparative → compare 策略，constraint → entity-aware，hypothetical → counterfactual
- [ ] 前端在 AI 气泡头部展示"自动选择策略：图增强"，用户可一键覆盖

**Microsoft GraphRAG（社区摘要式检索）**

在节点/章节级检索之上增加"社区摘要"层，对高层次抽象问题（如"液压系统相关规范的整体要求"）生成全局性回答。

- [ ] 使用 Neo4j GDS Louvain 算法对 Section 节点做社区检测，每个社区对应一个工艺主题簇
- [ ] 离线为每个社区生成 LLM 摘要，存入 `community_summaries` 表
- [ ] 问题路由：全局型问题 → 遍历社区摘要；局部型问题 → 现有向量/图检索
- [ ] `GET /api/graph/communities` 返回社区列表及其摘要，前端图谱以不同颜色区域渲染

**RAFT（检索增强微调）**

在微调数据集中混入"有噪声的干扰文档"，训练模型识别并忽略不相关上下文，专注真实依据。

- [ ] 构造 RAFT 数据集：每条样本包含 1 个相关章节 + 3 个干扰章节 + 标准答案（含 `<citation>` 标注）
- [ ] 与标准 SFT 数据集分批训练，对比 Faithfulness 指标，验证抗干扰能力提升效果

**ColBERT / ColPali 晚交互检索**

- [ ] 集成 ColBERT v2：不对 query 和 document 编码为单一向量，而是逐 token 交互后取最大相似度，提升长文本精确匹配
- [ ] ColPali：直接对 PDF 页面图像编码（Vision-Language Model），无需文字提取即可检索图文混排技术文档

---

### 十一、工业互联与数字孪生

将知识图谱从"文档知识"延伸至"实时工厂数据"，实现规范与现场的闭环。

**OPC-UA / IIoT 实时数据接入**

OPC-UA 是工业自动化领域的标准通信协议，覆盖 PLC、SCADA、DCS 等设备。

```
PLC / SCADA → OPC-UA Server → Python asyncua 客户端
    → 实时工艺参数（温度、压力、力矩、转速）
    → 与 Neo4j Constraint 节点比对
    → 超限自动告警：「当前液压压力 3150 PSI，超出 CPS1220 §4.3 规定上限 3000 PSI」
```

- [ ] `backend/src/services/opcua_monitor.py`：后台协程轮询 OPC-UA 节点，异常值触发 WebSocket 推送至前端
- [ ] Neo4j `Constraint` 节点新增 `opc_node_id` 属性，建立规范约束与实时采集点的绑定关系
- [ ] 管理后台"实时监控"页：展示当前各工位关键参数与规范约束的对比状态（绿/黄/红）

**数字孪生集成（Digital Twin）**

- [ ] 对接 Siemens Tecnomatix / ANSYS Twin Builder 数字孪生平台，当孪生模型仿真发现约束违规时，自动查询本系统相关工艺章节并返回处置建议
- [ ] `POST /api/twin/query`：接收数字孪生平台推送的异常事件（设备 ID + 参数名 + 当前值），返回对应工艺规范章节和整改措施
- [ ] 将仿真结果（虚拟工艺路线可行性分析）写入图谱，`(Process)-[:SIMULATED_BY]->(SimulationResult {pass: bool, deviation: float})`

**PDM / PLM 系统集成**

PDM/PLM 是工艺规范文档的权威来源，集成后可实现文档自动同步入库。

| 系统 | 集成方式 | 数据流向 |
|------|---------|---------|
| Siemens Teamcenter | REST API / ITK | 文档发布事件 → 自动触发 ETL 入库 |
| PTC Windchill | Windchill RPC / REST | 版本升版 → 自动更新 Neo4j `SUPERSEDES` 关系 |
| Dassault ENOVIA | 3DExperience API | ECO 发布 → 触发变更影响分析 |

- [ ] `scripts/plm_sync.py`：定时拉取 PLM "已发布" 状态文档，与本系统已入库文档对比，增量入库新版本
- [ ] Webhook 模式：PLM 侧配置 HTTP Callback，文档状态变更时主动推送至 `POST /api/webhooks/plm`

**ERP / MES 双向集成**

- [ ] **ERP（SAP PP/MM）**：查询工艺规范时，同步获取 SAP 中该零件的当前库存、替代件信息，纳入 LLM 上下文（"当前仓库中 HB5292 材料库存充足，可按规范执行"）
- [ ] **MES 工单关联**：将生产工单（Work Order）与对应工艺规范章节绑定，操作工扫码工单时 MES 自动推送相关规范摘要（免查找）
- [ ] `GET /api/mes/procedure?work_order_id=WO-2026-001`：MES 调用，返回该工单涉及的工艺步骤、工具清单、质量检验要求

---

### 十二、MLOps 与模型工程

从"手工部署模型"升级为可重复、可追溯、可自动迭代的机器学习工程体系。

**MLflow — 实验追踪与模型注册**

```
训练实验：epochs/lr/batch_size → MLflow Tracking
模型版本：bge-m3-finetuned-v1.2 → MLflow Registry（Staging → Production）
模型服务：MLflow Models → BentoML / Ray Serve 热部署
```

- [ ] `scripts/train_gnn.py` 改造：训练过程中写入 `mlflow.log_metric("loss", ...)` / `mlflow.log_param(...)`，每次训练自动注册新版本模型
- [ ] GNN 模型 Registry：`gnn-graphsage-v{n}` 版本链，对应不同规模的图谱数据集，支持一键回滚
- [ ] Reranker 微调后自动写入 Registry，通过 `PUT /api/admin/models/reranker/activate` 热切换生产版本

**Apache Airflow — ETL 与知识更新管线**

```
DAG: pdf_ingest_pipeline
  ├── 扫描 PLM 新文档 → 下载 PDF
  ├── ETL 解析（pdfplumber + OCR）
  ├── 实体提取（LLM）
  ├── Neo4j 写入
  ├── Milvus 向量化入库
  ├── GNN 增量训练触发
  └── 社区摘要更新（GraphRAG）
```

- [ ] `airflow/dags/ingest_pipeline.py`：每日 02:00 触发，幂等设计（已入库跳过），失败自动重试并钉钉告警
- [ ] `airflow/dags/graph_analytics.py`：每周日计算 PageRank / Betweenness，更新节点权重属性

**DVC — 训练数据版本控制**

- [ ] `dvc init`：将 GNN 训练图（`graph_snapshot_*.pt`）、RAGAS 评估数据集（`eval_qa_pairs.jsonl`）、微调数据集纳入 DVC 管理，存储至 MinIO / S3
- [ ] 每次模型训练自动关联对应数据集版本（`dvc repro`），确保实验完全可复现

**ONNX / TensorRT — 模型推理加速**

- [ ] BGE-M3 Embedding 导出为 ONNX 格式，使用 ONNX Runtime 推理（CPU 加速约 2×，GPU 加速约 5×）
- [ ] bge-reranker 导出 TensorRT Engine（适用 NVIDIA T4/A10），精排延迟从 80ms 降至 15ms
- [ ] 边缘部署场景：将量化后的 Embedding 模型（INT8）部署至车间工控机，无需联网即可完成向量化

**vLLM + PagedAttention — 高并发 LLM 服务**

- [ ] 替换现有 LLM 调用方式：本地部署 `vllm serve Qwen2.5-7B-Instruct --port 8001`，PagedAttention 将 GPU 显存利用率提升 3×，支持数十并发流式请求
- [ ] 前缀缓存（Prefix Caching）：相同系统提示的多个请求共享 KV Cache，与 Prompt Caching 策略协同

**Triton Inference Server — 统一模型服务网关**

- [ ] 将 BGE-M3、bge-reranker、GNN 推理、实体提取 LLM 统一部署至 Triton，通过 gRPC 调用
- [ ] 动态批处理（Dynamic Batching）：自动将同一时间窗口内的多个 Embedding 请求合并为一个批次，GPU 利用率从 20% 提升至 80%+

---

### 十三、企业级搜索增强

**Elasticsearch / OpenSearch Hybrid 混合搜索**

当前使用 Neo4j 全文索引（Lucene）+ Milvus 向量，可迁移至 OpenSearch 统一管理稀疏与稠密检索：

```
OpenSearch 8.x
  ├── BM25 全文检索（现有功能）
  ├── dense_vector 向量近似搜索（HNSW）
  ├── knn_vector + BM25 混合得分（linear_combination）
  └── 语义高亮（Semantic Highlighting）
```

- [ ] `scripts/migrate_to_opensearch.py`：将 Neo4j `Section.content` 批量索引至 OpenSearch，保留 Neo4j 作为图结构存储
- [ ] 混合检索公式：`score = α × BM25 + (1-α) × cosine_similarity`，α 可在管理后台按策略动态配置

**SPLADE — 稀疏学习向量**

SPLADE 是介于 BM25 和稠密向量之间的检索范式，既有稀疏可解释性，又有语义泛化能力。

- [ ] 集成 `naver/splade-cocondenser-selfdistil` 模型，为每个 Section 生成稀疏向量存入 Elasticsearch `sparse_vector` 字段
- [ ] 适合航空术语（如"CRES 钢"、"HB5292"）的精确匹配场景，BM25 的 OOV 问题显著改善

**ColBERT 晚交互检索**

- [ ] 使用 `stanford-oval/ColBERT` 建立二阶段管线：① 粗召回（向量 top-100）→ ② ColBERT MaxSim 精排（取 top-10）
- [ ] MaxSim 操作在 GPU 上并行计算，延迟增加 < 20ms，但 MRR@10 可提升约 15%

---

### 十四、多模态感知增强

**增强 OCR — 扫描版 PDF 解析**

当前 pdfplumber 依赖数字化 PDF，对扫描版文档效果差。

- [x] 集成 **PaddleOCR 3.0**（多语言 OCR，支持中文工程图纸）；扫描页自动检测并路由到 OCR 解析器
- [x] 版面分析（Layout Analysis）：PP-Structure 识别页面中的"正文/表格/图示"区域，分别用不同解析策略处理
- [x] **表格提取**：PP-Structure 表格区域 → HTML 解析 → 参数/值/单位列识别 → 写入 `Constraint` 节点（`source='table'`）

**工程图纸理解（Technical Drawing AI）**

- [x] 集成多模态 LLM（Qwen-VL / InternVL2）对机械工程图纸进行语义理解：提取零件编号、公差标注、装配关系
- [x] 将图纸中识别的约束（如"孔径 φ12 +0.02/-0.01 mm"）自动写入 `Constraint` 节点，关联对应 `Section`
- [x] 前端文档详情页：图纸缩略图可点击展开，AI 自动标注关键尺寸和公差带

**视觉质量检测（Visual QC AI）**

面向车间的 AI 质量检测，将检测结果反哺知识图谱。

- [ ] 集成 **YOLOv11** 或 **RT-DETR** 用于工件缺陷检测（划痕、裂纹、孔位偏差）
- [ ] 检测到缺陷时，自动查询知识图谱"该缺陷类型对应哪个工艺步骤的 Hazard 节点"，返回整改建议
- [ ] 缺陷样本写入图谱 `Defect` 节点，与 `Process` / `Material` 关联，积累缺陷模式知识库

**语音交互界面（Voice Interface）**

面向车间操作工的免手触交互场景。

- [ ] 集成 **Whisper Large-v3**（OpenAI）本地部署，实现车间噪音环境下的高准确率语音识别（中文工程术语 WER < 5%）
- [ ] 语音输入 → STT → 问答管线 → TTS 播报答案（使用 CosyVoice / ChatTTS）
- [ ] 前端新增语音模式：按住麦克风图标录音，松开触发查询，结果以文字 + 语音同步呈现
- [ ] 特殊指令："打开 CPS1220 第三章" / "显示液压系统图谱" → 联动前端路由跳转

**AR 辅助装配（Augmented Reality）**

- [ ] 基于 **WebXR API** 在平板/AR 眼镜上叠加工艺步骤指引，操作工看着实物即可看到对应工序说明
- [ ] 扫描零件条码 → 查询知识图谱 → AR 叠加显示：当前工序步骤、所需工具、力矩要求、安全警告
- [ ] 与 MES 工单系统联动：步骤完成后语音确认，自动记录到 MES 质量追溯数据

---

### 十五、实时事件流与数据管线

**Apache Kafka — 知识更新事件总线**

```
事件生产者                    Kafka Topics                    消费者
PLM 文档发布  ──────────►  doc.published        ──────►  ETL Pipeline（Airflow）
MES 工单创建  ──────────►  workorder.created    ──────►  规范推送服务
OPC-UA 告警   ──────────►  iot.constraint.alert ──────►  WebSocket 推送
用户查询日志  ──────────►  query.completed      ──────►  数据飞轮收集
图谱变更      ──────────►  graph.changed        ──────►  下游系统同步（ERP/MES）
```

- [ ] `docker-compose.yml` 新增 `kafka` + `zookeeper` 服务（或 Redpanda 单节点替代）
- [ ] `backend/src/events/producer.py`：文档入库、查询完成、图谱变更时发布 Kafka 消息
- [ ] `backend/src/events/consumer.py`：消费 OPC-UA 告警事件，触发规范查询并推送 WebSocket

**Change Data Capture（Debezium）**

- [ ] 部署 Debezium PostgreSQL Connector，捕获 `conversations` / `query_feedback` / `llm_usage` 表的变更事件
- [ ] 变更事件流入 Kafka，下游数据仓库（ClickHouse / Apache Doris）实时消费，支持亚秒级报表刷新

**Apache Flink — 实时图谱分析**

- [ ] 实时计算热点节点（滑动窗口 1 小时内被引用最多的 Section），动态更新 `Section.heat_score` 属性
- [ ] 实时检测约束违规流：OPC-UA 数据流 → Flink CEP（复杂事件处理）→ 检测"连续 3 次超限"模式 → 触发告警

---

### 十六、多智能体编排框架

**CrewAI — 角色制多 Agent 协同**

将复杂工艺分析任务分解为多个专业角色 Agent 协作完成：

```python
# 工艺评审 Crew 示例
crew = Crew(agents=[
    Agent(role="工艺规范检索员", tools=[query_knowledge_base, search_entities]),
    Agent(role="约束合规分析师", tools=[check_compliance, get_constraint_graph]),
    Agent(role="变更影响评估员", tools=[find_related_specs, trace_change_history]),
    Agent(role="报告撰写员",     tools=[generate_report]),
], process=Process.sequential)
```

- [ ] 场景一：**工艺变更评审**—— 输入 ECO 编号，Crew 自动完成：检索受影响章节 → 分析约束冲突 → 追踪下游规范 → 输出评审报告
- [ ] 场景二：**新员工培训问答**—— 教学 Agent 出题、解析 Agent 评分、辅导 Agent 针对错题提供章节引导

**AutoGen（Microsoft）— 对话式多 Agent**

- [ ] 实现"人类-AI 协作"工作流：用户在对话中逐步澄清需求，多个 Agent 分工迭代完善分析结果
- [ ] 专家校验模式：AI 给出初步分析 → 等待人类专家确认 → 继续下一步（Human-in-the-loop）

**Semantic Kernel — 微软 AI 编排 SDK**

- [ ] 对接 Semantic Kernel 的 Memory（向量存储）和 Planner（自动规划），与 Microsoft 365 / Azure AI 生态互通
- [ ] 适用于企业已采购 Microsoft Azure AI 服务的场景，快速实现与 SharePoint 文档库的双向同步

---

### 十七、知识图谱语义推理与标准化

**OWL / SPARQL — 语义 Web 标准**

- [ ] 将 Neo4j 图谱导出为 OWL 2 本体格式（`.ttl` Turtle 序列法），支持与 ATA iSpec 2200 / S1000D 等航空标准本体对接
- [ ] SPARQL 端点（通过 Apache Jena Fuseki）：允许外部系统以 SPARQL 查询本系统知识图谱，实现跨企业知识互操作
- [ ] SHACL 约束验证：定义 `SectionShape`（必须有 `content`、`doc_id`、至少一个关系）并在入库时自动校验，拒绝不合规节点写入

**知识图谱嵌入（KGE）— 链接预测**

| 模型 | 特点 | 适用场景 |
|------|------|---------|
| TransE | 简单高效，关系建模为向量平移 | 预测缺失的 `REFERENCES` / `REQUIRES_TOOL` 关系 |
| RotatE | 处理对称/反对称/传递关系 | 检测 `CONFLICTS_WITH` 潜在冲突对 |
| ComplEx | 复数空间，处理复杂关系模式 | 多跳关系推理（A→B→C 的隐含关联） |

- [ ] `scripts/train_kge.py`：使用 PyKEEN 框架训练 TransE / RotatE，预测置信度 > 0.8 的候选关系，推荐给管理员确认
- [ ] 链接预测结果融入检索：若预测到 `(SectionA)-[:SIMILAR_TO]->(SectionB)` 但图谱中尚未显式建边，召回时仍将 SectionB 纳入候选

**Neo4j GDS（图数据科学库）**

- [ ] **PageRank**：`CALL gds.pageRank.write('sectionGraph', {writeProperty: 'pagerank'})` 计算章节重要性，检索 RRF 公式新增 `+ γ × pagerank` 项
- [ ] **Louvain 社区检测**：划分工艺知识社区，结合 Microsoft GraphRAG 生成社区摘要
- [ ] **Node Similarity**：基于共享邻居计算节点相似度，自动建立 `SIMILAR_TO` 关系，填补语义边的密度
- [ ] **Betweenness Centrality**：识别图谱"桥接节点"（跨工艺领域的关键章节），在可视化中以特殊样式标注

---

### 十八、安全合规与企业集成

**AI 护栏（Guardrails）**

在 LLM 输出进入用户前，增加内容安全和格式校验层。

- [ ] 集成 **Guardrails AI**（`guardrails-ai`）：验证 LLM 输出必须包含来源引用、不得输出规范中不存在的参数值（幻觉检测）
- [ ] 集成 **NVIDIA NeMo Guardrails**：配置 `colang` 规则，屏蔽与航空工艺无关的话题（防止用户用工艺知识库进行无关查询），降低 API 成本
- [ ] 输出格式校验：Pydantic 模型强制 LLM 响应包含 `answer`、`sources`（非空）、`confidence` 三个字段，缺失时触发重试

**OPA（Open Policy Agent）— 细粒度访问控制**

- [ ] 将文档访问权限从"管理员/普通用户"二元模式升级为基于属性的访问控制（ABAC）
- [ ] OPA Policy 示例：`液压系统规范` 仅 `department=hydraulics OR role=admin` 可访问；涉密工艺章节需 `clearance_level >= 2`
- [ ] FastAPI 中间件在每次 `/api/query` 调用前向 OPA `POST /v1/data/authz/allow` 查询权限，拒绝时返回 403 并记录审计日志

**LDAP / SSO 统一认证**

- [ ] 集成企业 LDAP（Active Directory）：用户以域账号（工号 @corp.com）登录，无需单独维护密码，离职时 AD 禁用即自动失效
- [ ] SAML 2.0 / OIDC 支持：对接企业 SSO（钉钉、飞书、企业微信），移动端扫码登录
- [ ] 组织架构自动同步：从 AD 拉取部门树，自动更新用户 `department` 字段，无需手工维护

**区块链溯源（航空质量合规）**

航空制造的质量记录需满足 AS9100 / NADCAP 等标准的不可篡改要求。

- [ ] 集成 **Hyperledger Fabric** 或 **FISCO BCOS**（国产合规），将文档入库记录、工艺执行记录写入区块链
- [ ] 每次文档版本变更生成哈希上链：`{doc_id, version, sha256_hash, timestamp, operator}` → 链上存证
- [ ] `GET /api/audit/chain/{doc_id}`：返回该文档从创建至今的完整链上变更轨迹，适航审查时一键导出

**数据脱敏与隐私保护**

- [ ] 集成 **Microsoft Presidio**：对用户查询日志、LLM 上下文中的人名、工号、项目编号进行自动识别和脱敏后再落盘
- [ ] 差分隐私（Differential Privacy）：在分析报表（部门活跃度、查询热点）中对数据加噪，防止通过统计数据反推个人行为

---

### 十九、完整技术栈全景图

#### 当前已实现

| 层级 | 技术 | 状态 |
|------|------|------|
| 文档解析 | pdfplumber · pymupdf · 正则 ETL | ✅ |
| 向量检索 | Milvus 2.4 · BGE-M3 · bge-reranker | ✅ |
| 图检索 | Neo4j 5.20 · Cypher · BFS 扩展 | ✅ |
| 融合策略 | RRF · Parallel · Sequential · Graph-Aug · Multi-hop · GNN · Counterfactual | ✅ |
| Agent | LangGraph ReAct · 多跳推理链 | ✅ |
| 多模态 | GPT-4V / Qwen-VL 图片理解 · 图文关联查询 | ✅ |
| 可视化 | D3.js · Canvas · WebGL(PixiJS) · 热力图 · Timeline | ✅ |
| 可观测性 | Langfuse · LLM Cost Tracking · 用户活跃度报表 | ✅ |
| 基础设施 | Docker Compose · FastAPI · Next.js 15 · PostgreSQL · Redis | ✅ |

#### 近期规划（3-6 个月）

| 类别 | 技术 | 预期收益 |
|------|------|---------|
| RAG 增强 | HyDE · Adaptive RAG · CRAG | 召回率提升 15-25% |
| AI 生态 | MCP Server · Agent Skills | 融入 Claude/Cursor 工作流 |
| 模型优化 | LoRA 微调 · RAFT · DSPy | 幻觉率下降 30%+ |
| 推理加速 | vLLM · ONNX Runtime · Prompt Caching | 延迟降低 50%，成本降低 70% |
| 评估体系 | RAGAS · TruLens · MLflow | 建立量化效果基线 |
| 多模态 | 增强 OCR · 表格提取 · 语音接口 | 解锁扫描版文档 + 免手触场景 |

#### 中期规划（6-18 个月）

| 类别 | 技术 | 预期收益 |
|------|------|---------|
| 工业互联 | OPC-UA · 数字孪生 · PLM/MES 集成 | 规范与现场数据闭环 |
| 搜索增强 | SPLADE · ColBERT · OpenSearch Hybrid | 精确匹配 + 语义泛化双优 |
| 多 Agent | CrewAI · AutoGen · A2A 协议 | 复杂工艺分析自动化 |
| 图谱推理 | KGE（TransE/RotatE）· GDS · OWL/SPARQL | 链接预测 + 跨系统互操作 |
| MLOps | Airflow · DVC · Triton · TensorRT | 模型训练-部署全流程自动化 |
| 实时流 | Kafka · Flink · Debezium CDC | 知识实时更新 + 流式告警 |

#### 长期愿景（18 个月+）

| 类别 | 技术 | 场景 |
|------|------|------|
| 安全合规 | 区块链溯源 · OPA · LDAP/SSO | 适航审查 · NADCAP 合规 |
| 边缘 AI | ONNX INT8 量化 · 车间工控机部署 | 离网厂区 · 敏感数据本地化 |
| AR/VR | WebXR · AR 眼镜辅助装配 | 零纸化车间 · 操作引导 |
| 视觉质检 | YOLOv11 · RT-DETR · 缺陷图谱 | 在线视觉检测 + 质量追溯闭环 |
| 联邦学习 | PySyft · 多厂区知识聚合 | 数据不出厂的跨单位知识共享 |
