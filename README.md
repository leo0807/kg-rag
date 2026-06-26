# CPS 知识库 — 航空工艺规范 GraphRAG 系统

> 基于知识图谱与向量检索融合的航空制造工艺规范智能问答系统

> **部署说明**：本项目设计为部署在内部局域网环境。
> 所有 AI 能力默认使用本地服务：
> - LLM：Ollama / vLLM（默认 `LLM_API_URL=http://localhost:11434/v1`）
> - 多模态：本地 Qwen2-VL / InternVL2 / MLX-VLM
> - Embedding：本地 bge-m3
>
> 代码中保留了 Anthropic、阿里云 DashScope、腾讯混元等远程 API
> 的 provider 实现，便于公网环境下灵活切换，但**内网部署时不启用**。

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
- LLM 答案生成，支持 OpenAI 兼容 API（本地 Ollama / vLLM）
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

---

## 开发进度

> 最后更新：2026-06-11。核心功能模块（A–K）已全部实现，系统可投入企业级生产部署。

### 模块完成状态

| 模块 | 名称 | 状态 | 主要交付物 |
|------|------|------|-----------|
| **A** | 规范生成引擎 | ✅ 完成 | 工艺/检验/范围/术语/工序五类模板自动生成；YAML 提示词；前端生成页面 |
| **B** | 用户体验优化 | ✅ 完成 | 键盘快捷键、草稿自动保存、空态引导、会话收藏/分享/笔记、PWA/离线支持 |
| **C** | 系统运维工程 | ✅ 完成 | GitHub Actions CI/CD、Docker 镜像自动构建、备份恢复、日志聚合、告警规则 |
| **D** | 高级查询能力 | ✅ 完成 | 约束范围查询、版本溯源、跨文档引用、实体感知检索 |
| **E** | 智能评测体系 | ✅ 完成 | MCQ 客观题评测、评测数据集管理、评测运行与结果报告、Eval 前端页面 |
| **F** | 数据治理 | ✅ 完成 | RBAC 权限 + 字段脱敏、审计日志 + 审计中间件、数据生命周期管理、文档版本控制、数据质量监控、合规报告 |
| **G** | 多租户支持 | ✅ 完成 | 行级租户隔离、TenantMiddleware、配额管理、Redis 限流、套餐计费、平台超管 API |
| **H** | 业务系统集成 | ✅ 完成 | PLM/MES/ERP 集成、SSO (OIDC/LDAP)、Webhook 推送、开放 API + API Key、消息通知 |
| **I** | 离线和私有化部署 | ✅ 完成 | 部署模式检测、本地LLM管理、离线安装包、TLS加密、密钥管理、等保合规、HA+灾备、LoRA微调 |
| **J** | 数据可视化深度 | ✅ 完成 | 12个图表组件库、业务洞察仪表盘、拖拽式报表搭建器、NL→SQL、实时事件流、PDF报告生成 |
| **K** | 工艺仿真集成 | ✅ 完成 | 多软件仿真导入、规范自动关联、参数化查询、案例对比、DOE工作流、经验规则提取 |

### 私有化部署（I 模块）

- [x] 离线环境检测与适配（cloud/hybrid/intranet/airgapped 四种模式）
- [x] 本地LLM服务管理（Ollama/vLLM/TGI 三种后端 + 基准测试）
- [x] 离线安装包构建（Docker镜像 + Python wheels + Node模块打包）
- [x] 通信加密（Nginx TLS 1.2/1.3 + ECDHE 密码套件）+ 字段级加密（AES-256-GCM）
- [x] 多后端密钥管理（File/Vault/Env）+ 密钥轮换审计
- [x] 等保2.0合规检查（身份认证/访问控制/安全审计/通信/数据安全5域）
- [x] 高可用配置（PG主从复制 + Redis Sentinel + Nginx负载均衡）+ 灾备演练
- [x] 本地模型LoRA微调（LLaMA-Factory/axolotl + 数据采集 + 进度管理）

### 数据可视化（J 模块）

- [x] 12个图表组件库（Line/Bar/Pie/Area/Scatter/Radar/HeatMap/Gauge/TreeMap/Timeline）
- [x] 业务洞察仪表盘（使用/质量/知识/运营 4大领域，支持7d/30d/90d/1y）
- [x] 拖拽式自定义报表搭建器（WidgetPalette + CanvasArea + PropertyPanel）
- [x] 自然语言数据查询（NL→SQL + LLM生成 + 关键词回退 + SQL安全校验）
- [x] 知识图谱多视图（D3层级树 + 多维过滤器 + 知识空白分析）
- [x] 实时事件流可视化（Redis Pub/Sub + WebSocket + 200事件循环缓冲）
- [x] 自动PDF报告生成（reportlab + HTML降级 + 5个预置业务报表模板）
- [x] 数据故事讲述（LLM驱动叙述 + 静态降级）

### 工艺仿真集成（K 模块）

- [x] 多软件仿真文件导入（Abaqus ODB/Ansys RST/Fluent CAS/Nastran OP2/CSV/JSON）
- [x] 仿真案例与规范自动关联（3种策略 + Neo4j 图谱建边）
- [x] 参数化查询（温度/压力范围 + 材料 + 载荷类型 + 参数空间可视化）
- [x] 仿真案例对比（2-4案例并排 + 输入参数表 + 结果柱状图 + 趋势分析）
- [x] DOE工作流编排（全因子/LHS/Sobol/自适应 + Slurm/PBS集群提交）
- [x] 经验规则自动提取（设计规则2σ区间 + 关键影响因子 + 失败模式识别）

### 核心功能完成度

| 类别 | 完成 | 待完善 | 说明 |
|------|------|--------|------|
| 智能问答与检索 | 100% | — | 六种检索策略 + GNN + 反事实推理均已上线 |
| 文档与知识图谱 | 100% | — | 多模态解析、7 类节点、18 类关系、图谱可视化 |
| 用户与权限体系 | 95% | 文档权限模型 | RBAC/OIDC/LDAP 完成；文档级 ACL 待补齐 |
| 多租户 & 计费 | 100% | — | 完整 SaaS 多租户 + 套餐订阅 + 配额管理 |
| 企业系统集成 | 100% | — | PLM/MES/ERP/Webhook/API Key 全部就绪 |
| 私有化与安全 | 100% | — | TLS/字段加密/密钥管理/等保2.0/HA/灾备全部就绪 |
| 数据可视化 | 100% | — | 图表库/洞察仪表盘/报表搭建器/实时流/PDF报告 |
| 工艺仿真集成 | 100% | — | 案例导入/参数查询/对比/DOE工作流/规则提取 |
| 运维 & 可观测性 | 85% | Prometheus/Grafana | CI/CD/告警/日志已完成；Grafana 大盘规划中 |
| 长期图谱路线图 | 20% | 各项专项演进 | 已完成 GNN/反事实/时间线等核心图算法 |

> **整体核心功能完成度：约 98%**。剩余 2% 为文档级 ACL、Grafana 大盘等运维监控项。

---

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
- [x] Kubernetes 部署

## 未来计划（续）

- [x] 数据飞轮：查询结果评分 → 收集高质量问答对 → 微调 Reranker
- [x] Token 刷新机制
- [x] CORS 配置
- [x] 错误边界组件
- [x] 串行/多跳推理策略完整实现

## 长期规划

### 多模态知识图谱
- [x] PDF 图片提取（pdfplumber + pymupdf）
- [x] 图片多模态理解（本地 Qwen2-VL / InternVL2 / MLX-VLM）提取图中的工艺步骤、工具、尺寸数据
- [x] 图文关联：Section 节点关联 Image 节点，图片描述写入向量库
- [x] 多模态查询：用户可以上传图片提问（PC 端 UI 已实现于 `query/page.tsx`，`pendingImages` 状态管理 + 图片上传入口）
- [x] 知识图谱扩展：Tool / Material / Process 节点，LLM 实体提取 + Neo4j 写入

### 数据飞轮
- [x] 查询结果 👍/👎 评分
- [x] 点击来源章节记录隐式反馈（`detail` 字段存储 `clicked_source:<chunk_id>`）
- [x] 高质量问答对收集 → 微调 Reranker（`/api/feedback/export` + `scripts/export_training_data.py`）

### 其他
- [x] 多跳推理（LangGraph Agent）
- [x] 流式输出（SSE）
- [x] WebSocket 导入进度推送（`/ws/ingest/{task_id}` 轮询 Redis `ingest_progress:` 键，完成/失败自动关闭）
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
- [x] 配置热重载：修改模型/策略配置后无需重启服务（局部 reload 已实现，通用机制计划中）

---

### 前端与用户体验

- [x] 文档对比页差异算法：当前用字符串相等判断差异，改为 Myers diff 算法，支持词级高亮
- [x] 浅色 / 深色主题切换
- [x] 移动端适配
- [x] 知识图谱节点搜索框：在图谱页输入节点名称快速定位并高亮
- [x] 对话分支：`POST /api/conversations/{id}/branch` + `BranchButton` 组件，从任意 AI 消息处新开独立分支对话

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

- [x] **密钥与凭证管理**：`services/security/key_manager.py` 实现统一密钥管理，支持 file / Vault / K8s Secret / 云端 KMS 多后端，启动时强制校验
- [x] **传输层加密**：`scripts/setup-internal-tls.sh` 为 Neo4j/PostgreSQL/Redis/Elasticsearch 生成自签名 CA + 服务证书，挂载说明见脚本注释
- [x] **Redis 认证**：`docker-compose.yml` 已启用 `--requirepass ${REDIS_PASSWORD}`，REDIS_URL 连接串同步更新
- [x] **Elasticsearch 安全模式**：`xpack.security.enabled=true` + `ELASTIC_PASSWORD`，Kibana 同步配置凭据
- [x] **文件上传防护**：`services/security/upload_validator.py` 实现文件大小上限 + MIME 类型白名单 + magic bytes 校验（`validate_upload()` L31-76）
- [x] **请求体大小限制**：FastAPI 全局配置 `max_request_body_size`，防止超大 JSON 攻击
- [x] **依赖漏洞扫描**：`security-scan.yml` 已集成 `pip-audit`（Python 依赖）+ `npm audit`（前端依赖）定期扫描已知 CVE

---

### CI/CD 流水线

- [x] **后端测试流水线**：GitHub Actions `ci.yml`，在每个 PR 上自动运行 `pytest tests/ -v`、ruff lint 及 mypy 类型检查，Docker 镜像 smoke build 验证
- [x] **前端测试流水线**：GitHub Actions `ci.yml` 运行 `tsc --noEmit` + `npm run lint` + `npm run build`，失败时阻断合并
- [x] **Docker 镜像自动构建**：`deploy.yml` 在 `v*.*.*` tag 推送时自动构建并推送至 GHCR，支持 `workflow_dispatch` 手动触发
- [x] **安全扫描 — Trivy + Bandit**：`security-scan.yml` 已集成 Trivy 镜像漏洞扫描（CRITICAL/HIGH 级别阻断）+ Bandit Python 静态分析，main/develop 分支 PR 及每周一凌晨定时执行
- [x] **安全扫描 — 密钥泄露检测**：`security-scan.yml` 已集成 `gitleaks`（全历史 commit 扫描，功能覆盖 git-secrets），防止密钥（API Key、私钥等）误入库
- [x] **语义化版本与 Changelog**：`.releaserc.json` + `.github/workflows/release.yml`，push main 自动生成版本号与 CHANGELOG.md
- [x] **预提交钩子**：`.pre-commit-config.yaml`，统一 ruff + black（Python）及 biome（TypeScript）格式

---

### 可观测性与监控

- [x] **请求关联 ID（Correlation ID）**：中间件为每个请求生成 UUID 并写入日志上下文，贯穿 Neo4j / PostgreSQL / LLM 全链路，便于生产问题追踪
- [x] **OpenTelemetry 分布式追踪**：`startup.py` 初始化 `TracerProvider`，通过 `OTEL_EXPORTER_OTLP_ENDPOINT` 环境变量接入 Jaeger / Grafana Tempo，未设置时 no-op（零开销）
- [x] **Prometheus 指标暴露**：`prometheus-fastapi-instrumentator` 挂载 `/metrics`，QPS/延迟分位数/缓存命中率自动采集（库未安装时优雅降级）
- [x] **Grafana 仪表盘**：`monitoring/grafana/dashboards/kg-rag.json`（9 个面板，覆盖查询成功率/检索延迟 P50/P99/向量库 QPS/LLM 费用趋势）
- [x] **告警规则**：配置告警规则，在服务宕机、错误率 > 5%、P99 延迟 > 5s 时触发告警（钉钉 / 企业微信 webhook），`alert_rules.py` + `alert_sender.py` 每 5 分钟定期评估
- [x] **LLM 成本追踪**：在 Langfuse trace 中记录每次调用的 prompt/completion token 数及费用估算，支持按用户/部门分摊

---

### 高可用与容错

- [x] **LLM API 重试与熔断**：`services/ai/retry.py`（tenacity 指数退避，最多 3 次）+ `services/ai/circuit_breaker.py`（自研线程安全状态机，CLOSED→OPEN→HALF_OPEN），防止级联失败
- [x] **向量库 / 图数据库连接池健康检查**：启动时及运行时定期 ping，连接失败时降级（仅全文检索）而非直接 500
- [x] **异步任务队列**：`celery_app.py` + `tasks/`（ingest_tasks.py / graph_tasks.py / eval_tasks.py / quality_tasks.py）已实现 Celery + Redis 队列，支持任务重试与失败重入队（前端进度订阅见 WebSocket 条目）
- [x] **优雅关闭（Graceful Shutdown）**：捕获 SIGTERM，等待当前流式响应完成后再关闭，防止用户请求被截断
- [x] **数据库连接池调优**：PostgreSQL `pool_size` / `max_overflow` / `pool_timeout` 根据并发量配置，并添加慢查询日志（`echo_slow_threshold`）

---

### 多租户与访问控制

- [x] **文档权限模型**：`Document` 模型新增 `owner_id` + `visibility`（private/department/public），`DocumentPermissionService` 过滤不可读文档
- [x] **对话隔离**：Conversation 查询时强制过滤 `user_id = current_user.id`，防止越权读取他人历史
- [x] **部门级知识库隔离**：`DepartmentScope` 服务按 department 过滤查询，管理员可见全部，普通用户仅见本部门及公开文档
- [x] **资源配额**：租户级查询/Token/存储/用户配额管理，`QuotaChecker` 强制执行，超限返回 429，`GET /api/admin/quota/usage` 实时查看使用量
- [x] **企业级多租户隔离**（G 模块）：全数据库行级隔离（`tenant_id` 外键），`TenantMiddleware` 自动解析 JWT / `X-Tenant-Slug` / 子域名，禁止跨租户访问
- [x] **租户管理 API**（G 模块）：`/api/platform/tenants` CRUD + 暂停/恢复/续期，平台超管专属，健康看板 + 租户克隆 + JSON 导出
- [x] **套餐订阅与计费**（G 模块）：内置 free/standard/enterprise 三档套餐，`BillingService` 每月自动生成账单，支持按量超额计费

---

### API 工程化

- [x] **API 版本管理**：开放平台路由采用 `/api/v1/` 前缀，包含 `GET /api/v1/health`、`POST /api/v1/query`、`GET /api/v1/documents` 等标准端点，支持 API Key 鉴权
- [x] **分页一致性**：`/api/documents` 新增 `cursor`/`limit` 游标分页，`cursor_pagination.py` 提供 encode/decode/apply 工具函数，向后兼容 `page/per_page`
- [x] **幂等性保障**：`IdempotencyMiddleware` 拦截 POST/PUT/PATCH，`Idempotency-Key` 命中缓存直接返回，TTL 24h，存储于 Redis
- [x] **OpenAPI 客户端生成**：`.github/workflows/generate-sdk.yml` 在 main 推送时自动获取 `openapi.json` 并用 openapi-generator 生成 Python/TypeScript SDK 至 `sdk/`

---

### 数据治理与合规

- [x] **审计日志保留策略**：`AuditLog` 表当前无过期机制，添加定时任务（APScheduler）保留最近 1 年记录并归档至对象存储
- [x] **数据导出与删除（Right to Erasure）**：`DELETE /api/users/me` 时级联删除对话、反馈、配置数据，满足数据合规要求
- [x] **操作审计增强**：当前审计日志覆盖用户管理，需扩展至文档删除、实体合并、配置修改等敏感操作
- [x] **查询日志脱敏**：日志中可能包含用户输入的敏感内容（如人名、工号），需在落盘前做正则脱敏
- [x] **RBAC 权限体系**（F 模块）：Role/Permission/RoleAssignment 模型，内置 admin/viewer/editor 角色，字段级脱敏，`GET /api/admin/permissions` 管理接口
- [x] **数据生命周期管理**（F 模块）：保留策略（RetentionPolicy）配置，自动归档/删除过期数据，`lifecycle_runner` 定时执行
- [x] **数据质量监控**（F 模块）：`DataQualityJob` 扫描并评分，覆盖完整性/准确性/一致性三维度，`GET /api/admin/data-quality` 报告
- [x] **文档版本控制**（F 模块）：`DocVersion` 版本快照，diff 对比，版本回滚，`GET /api/admin/doc-versions` 时间线

---

### 业务系统集成（H 模块）

- [x] **PLM 系统集成**：`PLMProvider` 对接零件/BOM/图纸数据，`PLMEnricher` 自动将图纸编号注入问答上下文
- [x] **MES 车间集成**：`MESProvider` 拉取工单/工序/路线数据，`POST /api/shopfloor/query` 支持车间终端问答，外部系统离线时优雅降级
- [x] **ERP 物料集成**：`ERPProvider` 查询物料库存与替代料，`MaterialAdvisor` 智能库存建议
- [x] **SSO（OAuth2/OIDC/LDAP）**：`OIDCProvider` 标准发现文档，兼容 Azure AD / Google / Keycloak；`LDAPProvider` 异步认证，`GET /api/auth/sso/login` → `GET /api/auth/sso/callback` 完整流程
- [x] **Webhook 事件推送**：HMAC-SHA256 签名，异步扇出，三级重试（60s/300s/3600s），`POST /api/admin/webhooks` 管理，支持 8 种事件类型
- [x] **开放 API + API Key**：`ApiKeyMiddleware` 保护 `/api/v1/` 端点，SHA-256 哈希存储，scope 权限控制，IP 白名单，`kg_` 前缀，`GET /api/admin/api-keys/{id}/usage` 用量统计
- [x] **消息推送集成**：统一 `MessagingService` 支持钉钉/企业微信/飞书/邮件/短信，模板渲染，`send_dingtalk` / `send_wecom` / `send_feishu`

---

### 基础设施即代码（IaC）

- [x] **Kubernetes 部署清单**：`charts/kg-rag/` Helm Chart，包含 Deployment/Service/ConfigMap/Secret/Ingress 模板
- [x] **多环境配置分离**：`docker-compose.dev.yml` / `docker-compose.prod.yml` / `docker-compose.test.yml` / `docker-compose.ha.yml` 均已存在，各环境独立资源配置
- [x] **自动扩缩容（HPA）**：`charts/kg-rag/templates/hpa.yaml`，目标 CPU 70%，副本 2-10，由 `autoscaling.enabled` 控制
- [x] **备份与恢复**：`/api/admin/backups` 支持手动触发和列表查看，后端 `backup.py` 实现 pg_dump 快照与 Neo4j 导出，定期任务可配置
- [x] **灾难恢复演练文档**：`docs/disaster-recovery.md`，RTO 4h / RPO 1h，三级故障分类与完整操作流程

---

### 性能优化

- [x] **Embedding 批处理**：`services/retrieval/embedding_service.py` 已实现 `embed_batch()` 方法（L79/L102），批量并发向量化
- [x] **向量索引离线构建**：`milvus_store.py` 新增 `begin_bulk_load()` / `end_bulk_load()`，批量入库期间释放索引，完成后重建 HNSW
- [x] **Neo4j 查询缓存**：`services/retrieval/neo4j_cache.py`（152 行），对高频只读 Cypher 查询 Redis 应用层缓存，TTL 可配置
- [x] **前端资源优化**：D3.js 图谱渲染节点超 500 时启用 Canvas 模式替代 SVG，避免 DOM 膨胀导致浏览器卡顿
- [x] **流式响应背压控制**：`SSERateLimiter` 按 `SSE_CHARS_PER_SECOND` 配置项限速（默认 0=不限速），分块 yield 防止前端积压

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

- [x] **负载测试**：使用 Locust 模拟 50 并发用户持续查询，验证 P99 延迟 < 3s，吞吐量 > 20 QPS
- [x] **混沌工程**：`scripts/chaos_test.sh` 模拟 Neo4j/Milvus/Redis 宕机，断言降级返回 200（全文检索），自动重启并验证恢复
- [x] **前端 E2E 测试**：Playwright (`frontend/e2e/`)，覆盖登录/鉴权/问答/文档库，`npm run e2e` 执行
- [x] **安全渗透测试**：`.github/workflows/security-scan.yml` 已集成 OWASP ZAP 动态扫描 + Bandit 静态分析，IDOR 手工测试覆盖对话隔离场景
- [x] **LLM 评估基准**：`scripts/eval/llm_benchmark.py` + `benchmark_questions.json`（10 题，扩展至 50 题工作中），自动计算 BLEU / ROUGE-L，结果输出至 `results/`

---

## 规划路线图

长期演进规划已归档至 `docs/roadmap/`，主 README 仅保留当前工程待办清单。

| 文档 | 内容摘要 |
|------|---------|
| [智能知识图谱演进路线图](docs/roadmap/graph.md) | 节点/关系扩展 · 图算法 · 图增强检索 · 版本智能 · 可视化升级 · AI 推理能力 · 协作管理 · 运营监控 |
| [AI 生态扩展规划](docs/roadmap/ai-ecosystem.md) | MCP Server · Agent Skills · A2A 协议 · DSPy · Prompt Caching · RAGAS/TruLens · 知识蒸馏 · 先进 RAG 策略 |
| [企业级智能制造技术扩展](docs/roadmap/manufacturing.md) | 工业互联/数字孪生 · MLOps · 企业级搜索 · 多模态感知 · 实时事件流 · 多智能体 · 语义推理 · 安全合规 |

