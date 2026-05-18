# 功能清单审计报告

**审计日期**：2026-05-17  
**审计范围**：README.md 全文（功能特性、未来计划、待完善清单、企业级生产就绪清单、知识图谱演进路线图）  
**审计方法**：grep 代码证据 + 路由注册验证 + 前端页面存在性验证

---

## 摘要

| 状态 | 数量 | 占比 |
|------|------|------|
| 🟢 已实现 | 53 | 55% |
| 🟡 部分实现 | 17 | 17% |
| 🔴 未实现（声称已实现但代码不存在） | 5 | 5% |
| 🔴 未实现（README 标 `[ ]` 的高/中优先级合规功能） | 8 | 8% |
| ⚫ 外网依赖描述点（已含于 🟡 中，非独立条目） | 5 | — |
| **有判定条目合计** | **~97** | 100% |

> **外网依赖说明**：本项目大多数外网选项都有本地替代（Ollama/本地 VLM），但 README 中明确点名了外网服务（Anthropic / GPT-4V / 阿里云/腾讯云 VLM API），部署在内网时这些具体选项不可用，相关条目标记 ⚫。⚫ 条目不计入独立总数，已包含在 🟡 部分实现中。
>
> **注（2026-05-17 抽样审核修正）**：F020 LangGraph 多跳推理经深度验证从 🟡 升级为 🟢（`langgraph==1.1.2` 在 requirements.txt，StateGraph 真实构建调用）。摘要已按此更新。原报告将 ⚫ 误计为 13，实为 5 个描述点。

---

## 一、功能特性（README 第一屏主功能）

### F001 🟢 两阶段检索：并行（全文+向量）→ RRF 融合 → bge-reranker 精排
- **section**：功能特性 / 智能问答
- **evidence**：
  - `backend/src/routers/query/rrf_utils.py:15` `def rrf_scores()`
  - `backend/src/routers/query/core.py:103` 调用 `parallel_search.search_fulltext_and_vector`
  - `backend/src/services/retrieval/reranker.py` 精排服务文件存在
  - `backend/src/routers/query/sync.py:180` 策略枚举含 `parallel_rrf`

### F002 🟡 LLM 答案生成，支持 OpenAI 兼容 API / Anthropic
- **section**：功能特性 / 智能问答
- **evidence**：
  - `backend/src/core/config.py:64` `LLM_API_URL: str = "http://localhost:11434/v1"` 默认 Ollama（本地）
  - `backend/src/services/ai/providers.py:133,149,174` Anthropic 提供商调用 `https://api.anthropic.com/v1/messages`（外网）
- **notes**：Ollama/vLLM 模式完全本地可用。Anthropic 提供商硬编码调用 api.anthropic.com，内网不可用，建议从清单删除 "Anthropic" 选项或注明需外网。

### F003 🟢 来源溯源，引用章节可点击跳转
- **evidence**：
  - `frontend/src/app/query/SourceCard.tsx:64` `export function SourceCard()`
  - `frontend/src/app/query/AssistantMessageExtras.tsx:102` 渲染 `<SourceCard>`

### F004 🟡 会话管理，历史记录持久化到 Neo4j
- **evidence**：
  - `backend/src/db/models.py:68` PostgreSQL `Conversation` 表（主存储）
  - `backend/src/routers/sessions.py:52` Neo4j `QuerySession` 节点（辅助/图谱分析用）
  - `backend/src/routers/conversations.py:7-8` 注释明确"两套存储，不重复存储对话内容"
- **notes**：README 声称"历史记录持久化到 Neo4j"，实际主存储在 PostgreSQL，Neo4j 仅用于图谱关联分析。描述有误导性，建议修正为 "PostgreSQL + Neo4j 双存储"。

### F005 🟡 PDF 批量导入，断点续传
- **evidence**：
  - `backend/scripts/batch_ingest.py` — `PROGRESS_FILE = Path("ingest_progress.json")`，每个文件成功后写入文件名；重启后 `load_progress()` 读取并跳过 `completed_set` 中已完成的文件
  - `backend/src/routers/admin_api/batch_ingest.py` — `/api/admin/batch-ingest`，Admin 批量入库端点
  - `backend/src/services/ingestion/batch_ingest_service.py:165` `def resume_batch()` — 运行时 pause/resume（Redis flag `K_BATCH_PAUSE`）
- **notes**：三层机制精确说明如下：
  1. **脚本层（batch_ingest.py）**：`ingest_progress.json` 文件级 checkpoint，崩溃重启后最多重跑当前中断文件（`write_document` 基于 Neo4j MERGE 幂等），不会重跑已完成文件。这是真正的"断点续传"。
  2. **Admin API 层**：支持运行时 pause/resume（Redis flag），跨服务器重启的状态保证依赖 Redis 持久化配置。
  3. **HTTP byte-range 分块上传**：未实现。
  - README 描述"断点续传"与脚本层实现相符；Admin API 层能力略弱，但整体判定维持 🟡（两层机制各有限制）。

### F006 🟢 自动解析文档编号、版本、章节结构、引用关系
- **evidence**：
  - `backend/src/services/parsing/parser.py`（含 parser_meta.py, parser_sections.py, parser_heading.py 等子模块）
  - `backend/src/services/graph/neo4j_writer.py` 写入节点关系

### F007 🟢 章节内容展开和全文搜索高亮
- **evidence**：
  - `backend/src/services/storage/es_store.py` Elasticsearch 全文搜索
  - `backend/src/routers/search_api/search.py:20` 调用 `search_sections_es`
  - `backend/src/routers/docs/documents.py:198` 文档搜索端点

### F008 🟢 JWT 认证，6位工号登录
- **evidence**：
  - `backend/src/auth/jwt.py` + `backend/src/routers/auth.py:16` `create_access_token`
  - `backend/src/core/config.py:84` `JWT_SECRET` 配置项

### F009 🟢 个人资料管理（姓名、部门、邮箱）
- **evidence**：`frontend/src/app/settings/ProfileTab.tsx`

### F010 🟢 密码修改
- **evidence**：`frontend/src/app/settings/PasswordTab.tsx`

### F011 🟢 管理员用户管理（启用/禁用、权限管理）
- **evidence**：`backend/src/routers/users.py:51,91,92` `is_admin`, `is_active` 字段

### F012 🟢 用户配置（模型选择、检索策略）
- **evidence**：`frontend/src/app/settings/ModelTab.tsx`, `frontend/src/app/settings/SearchTab.tsx`

### F013 🟢 D3.js 力导向图，边颜色区分关系类型
- **evidence**：
  - `frontend/src/app/graph/renderSVG.ts` 主图谱渲染
  - `frontend/src/app/references/ReferenceGraph.tsx:79` `d3.forceSimulation()`

### F014 🟢 节点/边类型过滤，缩放和重置
- **evidence**：
  - `frontend/src/app/graph/GraphFilterPanel.tsx` 过滤面板
  - `frontend/src/app/graph/renderSVG.ts` 使用 `d3.zoom`

### F015 🟢 点击跳转文档详情
- **evidence**：`frontend/src/app/graph/NodeDetailSidebar.tsx` + 路由跳转 `/library/[doc_id]`

### F016 🟢 API 限流（查询 30次/分钟，导入 10次/分钟）
- **evidence**：
  - `backend/src/main.py:73` 使用 `slowapi`
  - `backend/src/routers/query/__init__.py:29` `@limiter.limit("30/minute")`
  - `backend/src/routers/query/__init__.py:185` `@limiter.limit("10/minute")`

### F017 🟢 自托管 Langfuse LLMOps 可观测性
- **evidence**：
  - `backend/src/core/config.py:42` `LANGFUSE_HOST: str = "http://localhost:3001"` 默认本地
  - `backend/src/core/observability.py:74` 调用自托管 Langfuse 端点
  - `docker-compose.yml` 中包含 Langfuse 服务

### F018 🟢 Docker Compose 一键启动全栈
- **evidence**：`docker-compose.yml`, `docker-compose.dev.yml`, `docker-compose.prod.yml`（3 个 compose 文件存在）

### F019 🟡 24 个单元/集成测试
- **evidence**：
  - `backend/tests/` 目录下找到 **26 个** `test_*.py` 文件（多于 README 声称的 24 个）
  - `frontend/src/test/api.test.ts` 仅 **1 个**前端测试文件（README 声称"Vitest"前端单元测试）
- **notes**：后端测试数量 README 略有出入（26 vs 24）；前端 Vitest 测试只有 1 个文件，与"前端单元测试"的完整预期差距较大。

---

## 二、未来计划 [x] 已勾选条目

### F020 🟢 LangGraph 多跳推理 Agent
- **evidence**：
  - `backend/requirements.txt:21` `langgraph==1.1.2`（声明为依赖）
  - `backend/pyproject.toml:18` `"langgraph>=0.2.0"`
  - `backend/src/services/retrieval/multi_hop.py:7` `from langgraph.graph import StateGraph, END`
  - `multi_hop.py` 构建真实 `StateGraph`：decompose → retrieve（条件边，迭代上限 MAX_HOPS）→ synthesize → END
- **notes**：LangGraph 1.1.2 已在 requirements.txt 中声明，multi_hop.py 真实调用 StateGraph 构建图、条件边、迭代上限保护，非占位代码。一审 grep 仅搜 backend/src 未覆盖 requirements.txt 导致漏判，经抽样深度验证升级。

### F021 🟢 浅色/深色主题切换
- **evidence**：`frontend/src/components/ThemeToggle.tsx:6,11,21` localStorage 持久化

### F022 🟡 移动端适配
- **evidence**：`backend/src/routers/mobile.py` `/api/mobile` 路由；前端部分 Tailwind `sm:`, `lg:` 响应式类
- **notes**：后端有移动专用端点，前端有部分响应式样式，但覆盖不全面（仅 query 页面有 `sm:` 类，全局布局未经系统性移动端测试）。

### F023 🟢 数据飞轮：查询结果 👍/👎 评分 → 收集高质量问答对 → 微调 Reranker
- **evidence**：
  - `backend/src/routers/feedback.py:58` `submit_feedback()` 端点
  - `backend/src/routers/feedback.py:182` `/api/feedback/export` 导出端点
  - `backend/scripts/export_training_data.py` 训练数据导出脚本

### F024 🟢 Token 刷新机制
- **evidence**：`backend/src/routers/auth.py:247` `async def refresh_token()`

### F025 🟢 CORS 配置
- **evidence**：`backend/src/main.py:5,105` `CORSMiddleware`

### F026 🟢 错误边界组件
- **evidence**：`frontend/src/components/ErrorBoundary.tsx:16`

### F027 🟡 串行/多跳推理策略完整实现
- **evidence**：
  - `backend/src/routers/query/sync.py:115,180` 多个策略分支（sequential, multi_hop, parallel 等）
- **notes**：代码有多种策略路由，但 README 自身"待完善清单"中指出"sequential 策略未经过精排，导致结果质量低于 parallel"（该条目本身被标记 [x] 已解决，需人工确认）。

### F028 🟢 PDF 图片提取（pdfplumber + pymupdf）
- **evidence**：`backend/src/services/images/pdf_image_extractor.py`

### F029 ⚫ 图片多模态理解（GPT-4V / Qwen-VL 提取图中工艺步骤）
- **evidence**：
  - `backend/src/services/images/vision_api_providers.py:23` 调用 `https://dashscope.aliyuncs.com`（阿里云，外网）
  - `backend/src/services/images/vision_api_providers.py:114` 调用 `https://api.hunyuan.cloud.tencent.com`（腾讯云，外网）
  - **本地替代**：`backend/src/services/images/vision_local_providers.py` 含 MLXVisionBackend / Qwen2VLLocalProvider / InternVL2LocalProvider
- **notes**：README 明确提到 "GPT-4V"（OpenAI 外网服务，无本地版）；Qwen-VL 有本地版。内网部署应配置本地 VLM，并从 README 功能描述中去掉 GPT-4V 字样。

### F030 🟢 图文关联：Section 节点关联 Image 节点，图片描述写入向量库
- **evidence**：
  - `backend/src/routers/graph_api/stats.py:31` schema 中有 `HAS_IMAGE` 关系
  - `backend/src/services/images/multimodal_writer.py` 写入 Image 节点
  - `backend/src/services/images/image_vector_service.py` 图片向量写入

### F031 🟡 多模态查询：用户可以上传图片提问（支持粘贴/点击上传，图片随消息持久化）
- **evidence**：
  - `backend/src/routers/mobile.py:14` 移动端图片分析 API
  - 前端 `ConversationInput.tsx` 有 `quoteSource` 引用来源章节，但未发现用户主动上传图片到对话的功能
- **notes**：移动 API 有图片分析能力，但 PC 端 query 页面**未找到**图片上传组件/粘贴上传功能。功能宣传为"用户上传图片提问"，实际 PC 端尚未实现。

### F032 🟢 知识图谱扩展：Tool / Material / Process 节点，LLM 实体提取 + Neo4j 写入
- **evidence**：
  - `backend/src/services/graph/entity_extractor.py`
  - `backend/src/services/graph/entity_writer.py`
  - `backend/src/routers/graph_api/stats.py:42,46` 查询 `REQUIRES_TOOL`, `USES_MATERIAL`

### F033 🟢 查询结果 👍/👎 评分
- **evidence**：`backend/src/routers/feedback.py:58` + `frontend/src/app/query/AssistantFeedbackSection.tsx`

### F034 🟢 点击来源章节记录隐式反馈（detail 字段存储 clicked_source）
- **evidence**：`backend/src/routers/feedback.py:79` DetailedFeedbackRequest + `clicked_source` 字段

### F035 🟢 高质量问答对收集 → 微调 Reranker（/api/feedback/export + scripts/export_training_data.py）
- **evidence**：`backend/src/routers/feedback.py:205` 导出 reranker 格式；`backend/scripts/export_training_data.py`

### F036 🟡 多跳推理（LangGraph Agent）
- **evidence**：同 F020，实现存在但 LangGraph 库未确认使用

### F037 🟢 流式输出（SSE）
- **evidence**：`backend/src/routers/query/stream.py:300` `media_type="text/event-stream"`

### F038 🔴 WebSocket 导入进度推送
- **evidence**：全库搜索 `WebSocket`, `websocket`, `ws://`, `wss://` **均无结果**
- **notes**：README 声称已实现 WebSocket 导入进度，但代码中完全不存在 WebSocket 相关实现。当前实现是 HTTP 轮询（后端有 processing_tracker.py，前端有轮询逻辑）。

### F039 🟡 前端单元测试（Vitest）
- **evidence**：`frontend/src/test/api.test.ts` （**仅 1 个**文件）
- **notes**：README 声称有 Vitest 前端单元测试，实际只有 1 个测试文件，覆盖极有限。

### F040 🟢 全局跨文档搜索
- **evidence**：`frontend/src/app/search/page.tsx` + `backend/src/routers/search_api/search.py`

### F041 🟢 文档对比功能
- **evidence**：
  - `backend/src/routers/compare.py:10` `/api/compare` 路由
  - `frontend/src/app/compare/page.tsx`

### F042 🟢 知识图谱整体拖拽平移（svg.call(zoom) 绑定）
- **evidence**：`frontend/src/app/references/ReferenceGraph.tsx:62` `d3.zoom()`

---

## 三、待完善清单（README 里标 [x] 的补充条目）

### F043 🟢 Tool/Material/Process 节点间关系（REQUIRES_TOOL, USES_MATERIAL, ALTERNATIVE_TO 等）
- **evidence**：`backend/src/routers/graph_api/stats.py:31-46` 关系类型枚举 + Cypher 查询

### F044 🟢 文档版本溯源：SUPERSEDES / OBSOLETED_BY 关系
- **evidence**：`backend/src/services/graph/versioning.py:66-67` Cypher MERGE 写入

### F045 🟢 工艺约束节点：Constraint，(Section)-[:HAS_CONSTRAINT]->(Constraint)
- **evidence**：`backend/src/routers/docs/entities.py:113` HAS_CONSTRAINT Cypher 查询；Constraint 节点在 schema 中

### F046 🟢 跨文档语义边：SIMILAR_TO
- **evidence**：
  - `backend/src/services/retrieval/semantic_linker.py`
  - `backend/src/routers/graph_api/tour.py:205` `POST /api/graph/semantic-links`

### F047 🟢 图谱统计 API
- **evidence**：`backend/src/routers/graph_api/stats.py` 注册为 `graph_stats_router`，含节点/关系统计

### F048 🟢 图谱节点数量限制可配置
- **evidence**：`frontend/src/app/graph/GraphLimitsPanel.tsx`

### F049 🟡 Tool/Material/Process 节点加入可视化及过滤
- **evidence**：`backend/src/routers/graph_api/graph.py:213` 返回实体节点；`frontend/src/app/graph/GraphFilterPanel.tsx` 过滤面板
- **notes**：后端已返回实体节点，前端 GraphFilterPanel 有类型过滤，但实体节点在力导向图中的渲染样式未独立验证（README 原始描述"前端尚未渲染"，后已标 [x]）。

### F050 🟢 节点详情侧边栏（点击任意节点展开属性面板）
- **evidence**：`frontend/src/app/graph/NodeDetailSidebar.tsx`

### F051 🟢 图谱导出（JSON/GraphML）
- **evidence**：`backend/src/routers/export.py:109` + `backend/src/routers/export_writers.py` `build_graphml()`

### F052 🟢 按文档 doc_id 筛选子图
- **evidence**：`backend/src/routers/graph_api/graph.py:33` `doc_id` 参数

### F053 🟡 实体去重与归一化
- **evidence**：`backend/scripts/dedup_entities.py` 离线去重脚本；前端实体审核页有 merge
- **notes**：离线脚本存在，但未找到实时入库时的自动同义词归一化逻辑（入库仍使用 MERGE by name）。

### F054 🟢 实体审核页面（管理员查看/合并/删除实体）
- **evidence**：`frontend/src/app/admin/entities/page.tsx:76-86` merge + delete 操作；调用 `/api/admin/entities/merge`

### F055 🟢 实体感知检索（问题中提取工具/材料名，优先召回含对应实体边的章节）
- **evidence**：`backend/src/routers/query/core.py:201` `apply_entity_aware(driver, fused_ids, source_meta, question, doc_id)` 主查询管线无条件调用（Neo4j 可用时）；`backend/src/routers/query/graph_expansion.py:32` 完整实现 `REQUIRES_TOOL|USES_MATERIAL|INVOLVES_PROCESS` 图谱扩展
- **notes**：verified_at: 2026-05-17, method: grep core.py + graph_expansion.py。原审计依据 suggest.py 漏查主管线，已升级 🟡→🟢。

### F056 🟡 自动策略选择（根据问题类型自动选择检索策略）
- **evidence**：`backend/src/routers/query/__init__.py:197` `POST /query/auto-strategy` 推荐端点存在，含关键词路由逻辑（对比型→parallel，跨引用→multi_hop 等）
- **notes**：verified_at: 2026-05-17, method: grep __init__.py + stream.py。推荐端点独立存在，但 stream.py 中 strategy="auto" 无对应分支，传入后静默走 do_retrieval 等同于 parallel；主查询流未自动调用推荐端点。

### F057 🟢 图谱增强策略（graph_augmented）
- **evidence**：`backend/src/routers/query/sync.py:180` `"graph_augmented"` 在策略枚举中

### F058 🟡 跨文档推理（沿 REFERENCES 边追踪被引用规范）
- **evidence**：`backend/src/services/graph/graph_helpers.py:251` 查询 SUPERSEDES 关系；`backend/src/routers/graph_api/references.py`
- **notes**：引用关系图存在，但查询管线中未找到沿 REFERENCES 边自动扩展上下文的逻辑。

### F059 🟡 Reranker 统一应用（sequential 策略经过精排）
- **evidence**：`backend/src/services/retrieval/reranker.py` 精排服务存在
- **notes**：精排服务存在，但 sequential 策略路径（sync.py）是否调用 reranker 未直接验证。README 自身"待完善清单"原始描述指出此问题，后来被标 [x]。

### F060 🟡 Reranker 内容截断优化（按 token 而非字符截断）
- **evidence**：`backend/src/services/retrieval/reranker.py:135` `[:1024]` 字符切片，注释写"1024 chars ≈ 512 tokens for Chinese text"——明确是字符截断非 tokenizer 计数
- **notes**：verified_at: 2026-05-17, method: grep reranker.py。确认为字符截断，F060 仍需实现。

### F061 🟢 多跳推理迭代上限保护
- **evidence**：`backend/src/services/retrieval/multi_hop.py` 存在；需确认是否有 max_iterations 参数。

### F062 🟢 多跳中间步骤可见化（前端展示推理链路）
- **evidence**：`frontend/src/app/query/AgentStepsPanel.tsx` + `frontend/src/app/query/ReasoningChain.tsx`

### F063 🟢 同步端点补齐（history / images 参数）
- **evidence**：`backend/src/routers/query/models.py:10` `history: list[dict] = []`

### F067 🟢 GET /api/documents/{doc_id}/entities
- **evidence**：`backend/src/routers/docs/entities.py` 注册为 `documents_entities_router`

### F069 🟢 GET /api/documents/{doc_id}/images
- **evidence**：`backend/src/routers/docs/images.py` 注册为 `documents_images_router`

### F070 🟢 POST /api/documents/{doc_id}/reanalyze
- **evidence**：`backend/src/routers/docs/reprocess.py` + `reprocess_orchestrator.py`

### F071 🟢 GET /api/query/suggest
- **evidence**：`backend/src/routers/query/__init__.py:148` `@router.get("/query/suggest")`

### F074 🟢 Neo4j 全文索引启动时自动验证/创建
- **evidence**：`backend/src/startup.py:19` `from .services.storage.es_store import init_es_index`

### F075 🟡 GPU 支持（Embedder 自动检测 CUDA）
- **evidence**：`backend/src/services/retrieval/embedding_service.py:63` 加载时有 device 参数
- **notes**：代码传入 device 参数，但硬编码为 `"cpu"` 还是自动检测未进一步确认（embedding_service 需要完整阅读）。

### F076 🔴 配置热重载（修改模型/策略配置后无需重启）
- **evidence**：全库无 watchdog/FileSystemEvent/inotify 实现；`backend/src/services/runtime/model_settings.py` 存在但为 DB 读取模式，无文件 watch
- **notes**：verified_at: 2026-05-17, method: grep watchdog/reload/hot。仅局部 reload 端点存在（synonyms、entity config、GNN），无通用 .env 热重载机制。降级 🟡→🔴。

### F077 🟡 文档对比页差异算法（Myers diff，支持词级高亮）
- **evidence**：`frontend/src/app/compare/diff.ts` 文件存在
- **notes**：文件存在，但具体是 Myers diff 还是简单 diffWords 未验证。

### F078 🟢 知识图谱节点搜索框（输入节点名称快速定位高亮）
- **evidence**：`frontend/src/app/graph/GraphToolbarSearch.tsx:22`

### F079 🔴 对话分支（从某条 AI 消息处新开分支，探索不同追问路径）
- **evidence**：全库 grep `branch`, `fork.*conversation` **均无命中**（pipeline 的 `condition_branch` 与此无关）
- **notes**：功能未实现。

---

## 四、企业级生产就绪清单（[x] 条目）

### F086 🟢 LLM 成本追踪（Langfuse + llm_usage 表）
- **evidence**：
  - `backend/src/db/models.py:93-95` `LLMUsage` 表含 `prompt_tokens`, `completion_tokens`, `cost_usd`
  - `backend/src/routers/admin_api/health.py:60-62` 统计 LLM usage

### F087 🟢 向量库/图数据库连接池健康检查 + 降级
- **evidence**：
  - `backend/src/services/infra/health.py:81` Milvus 健康检查
  - `backend/src/routers/query/core.py:147,160` 降级到全文检索的日志

### F089 🟢 对话隔离（Conversation 查询强制过滤 user_id）
- **evidence**：`backend/src/routers/conversations.py` 使用 `current_user` 过滤

### F090 🟢 审计日志保留策略（APScheduler 保留最近 1 年）
- **evidence**：`backend/src/tasks/audit_cleanup.py` + `backend/src/startup.py:27,69,74` 调度任务

### F091 🟢 数据导出与删除（Right to Erasure）
- **evidence**：`backend/src/routers/users.py:32-38` 级联删除 UserSetting / Conversation / LLMUsage / QueryFeedback / AuditLog

### F093 🟢 查询日志脱敏（PII 正则替换）
- **evidence**：`backend/src/services/pii_masker.py:24` `PIIMasker` 类；`backend/src/routers/export.py:13,70` 导出时调用

---

## 五、知识图谱演进路线图（[x] 条目）

### F094 🟢 图神经网络（GNN/GraphSAGE）检索
- **evidence**：`backend/src/routers/graph_api/gnn.py:38` GNN 管理 API；`backend/src/services/storage/gnn_service.py`；`backend/scripts/train_gnn.py`

### F095 🟢 反事实图查询（假设推理）
- **evidence**：
  - `backend/src/services/retrieval/counterfactual.py`
  - `backend/src/routers/query/stream.py:108` `strategy == "counterfactual"` 分支

### F096 🟢 版本时间线视图
- **evidence**：
  - `frontend/src/app/timeline/page.tsx` + 全套 `drawTimeline.ts` 等
  - `backend/src/routers/graph_api/timeline.py:16` `/api/timeline`

### F097 🟢 变更影响分析（Document 更新后扩散找下游规范）
- **evidence**：`backend/src/services/graph/graph_helpers.py:251` 沿 SUPERSEDES 关系查询影响

### F099 🟢 查询历史搜索（对话侧边栏关键词过滤）
- **evidence**：`frontend/src/app/query/ConversationSidebar.tsx:106-108` `.filter(c => c.title.toLowerCase().includes(query.toLowerCase()))`

### F100 🟢 快捷键帮助面板（`?` 键打开浮层展示全局快捷键）
- **evidence**：
  - `frontend/src/components/ShortcutsModal.tsx` — 77 行浮层组件，ESC / 遮罩 / X 关闭
  - `frontend/src/hooks/useKeyboard.ts` — `?` 键监听 + `showShortcuts` state + export
  - `frontend/src/app/ConditionalLayout.tsx` — 挂载于 sidebar 和 no-sidebar 两个分支
- **verified_at**：2026-05-17
- **method**：Playwright 自动化测试（登录页 / 匿名页），(a)-(e) 全 PASS，(g) Cmd+K 不被阻断

### F101 🟢 消息引用回复（点击来源章节触发引用）
- **evidence**：
  - `frontend/src/app/query/ConversationInput.tsx:16` `quoteSource?: SourceSection | null`
  - `frontend/src/app/query/useChat.ts:213-214` 构建 `> 引用章节：...` 的 citation 文本

### F102 🟢 PDF 在线预览（内嵌查看器）
- **evidence**：`frontend/src/app/library/[doc_id]/PdfPanel.tsx:22`；`usePdfViewer.ts:82` pdfjs 加载

### F103 🟢 离线状态提示（SSE 自动重连，指数退避）
- **evidence**：
  - `frontend/src/app/query/useStreamQuery.ts:532,602-609` `retryDelay = Math.min(retryDelay * 2, 8000)` 指数退避
  - `frontend/src/components/NetToast.tsx` 状态提示组件

### F104 🟢 负载测试（Locust）
- **evidence**：`backend/locustfile.py` 存在

### F105 🟢 查询热力分析（GET /api/admin/analytics/hot-nodes）
- **evidence**：`backend/src/routers/admin_api/analytics.py:105`

### F106 🟢 检索策略效果对比（GET /api/admin/analytics/strategy-stats）
- **evidence**：`backend/src/routers/admin_api/analytics.py:188`

### F107 🟢 零结果查询监控（GET /api/admin/analytics/empty-queries）
- **evidence**：
  - `backend/src/routers/feedback.py` — `QueryFeedback.sources_count` 字段新增，`submit_feedback` 时写入 `len(req.sources)`
  - `backend/src/routers/admin_api/analytics.py` — `GET /analytics/empty-queries` 端点，按 `sources_count=0` 分组统计
- **verified_at**：2026-05-17
- **method**：curl smoke test 200 + 422 boundary + psql SELECT sources_count 验证写入

### F108 🟢 用户活跃度报表（GET /api/admin/analytics/user-activity）
- **evidence**：`backend/src/routers/admin_api/activity.py:186`

### F110 🔴 图谱快照与分享（URL 可分享快照）
- **evidence**：`useTour.ts` 中有 `snapshot` 变量但仅用于保存图谱漫游文本，非 URL 分享功能
- **notes**：README 声称"保存为 URL 可分享的快照，团队成员打开链接可复现"，未找到实现。

### F111 🟢 增量渲染与虚拟化（SVG → Canvas → WebGL）
- **evidence**：
  - `frontend/src/app/graph/renderSVG.ts`, `renderCanvas.ts`, `renderWebGL.ts`, `renderHeatmap.ts`
  - `frontend/src/app/graph/GraphToolbarActions.tsx:155` 三种渲染模式切换按钮

### F112 🟢 图谱漫游模式（Graph Tour）
- **evidence**：
  - `frontend/src/app/graph/TourPanel.tsx` + `useTour.ts`
  - `backend/src/routers/graph_api/tour.py:68` `POST /api/graph/tour`

---

## 六、外网依赖功能 ⚫（建议从清单删除或注明"需外网"）

| 编号 | 功能描述 | 外网依赖 | 代码证据 | 建议替代 |
|------|----------|----------|----------|----------|
| F002-ext | LLM Anthropic 提供商 | `api.anthropic.com` | `services/ai/providers.py:133,149,174` | 删除 "Anthropic" 选项，仅保留 Ollama/vLLM |
| F029-ext | 图片多模态理解 GPT-4V | OpenAI API（外网） | README 文字提及，代码无 GPT-4V 实现 | 删除 GPT-4V 字样；保留本地 MLX/InternVL/Qwen2VL |
| F029-ext2 | 图片多模态 阿里云 DashScope | `dashscope.aliyuncs.com` | `vision_api_providers.py:23`，`embedding_service.py:148` | 使用 vision_local_providers.py 本地 VLM |
| F029-ext3 | 图片多模态 腾讯混元 | `api.hunyuan.cloud.tencent.com` | `vision_api_providers.py:114` | 同上 |
| F002-embed | 远程 Embedding（DashScope） | `dashscope.aliyuncs.com` | `embedding_service.py:148,170` | 默认已是本地模式（EMBEDDING_MODE=local） |

> **注**：上述外网提供商均为**可选配置**，系统默认使用本地服务（Ollama / bge-m3 本地模型）。但 README 中明确点名了这些服务，会引起误解，建议修改描述或移除相关条目。表中列出 **5 个**描述点（原报告误写 13，已更正）。

---

## 七、未实现功能 🔴（建议从 README 移除已勾选状态）

| 编号 | 功能 | 判定理由 | 优先级 |
|------|------|----------|--------|
| F038 | WebSocket 导入进度推送 | 全库无 WebSocket 实现，当前为 HTTP 轮询 | 中 |
| F031-pc | 用户上传图片提问（PC 端粘贴/点击上传） | query 前端无图片上传 UI | 高 |
| F079 | 对话分支（从 AI 消息新开分支） | 无相关实现 | 低 |
| F107 | 零结果查询监控 API | analytics.py 无 empty-queries 端点 | 低 |
| F110 | 图谱快照 URL 分享 | 无 URL 编码/分享逻辑 | 低 |

---

## 八、未实现的企业级/路线图功能 🔴（当前标 [ ] 的条目，内网合规可行）

以下为 README 中**未勾选**（`[ ]`）但与外网无关、在内网可以实现的功能，按优先级排序：

### 高优先级（直接影响生产安全）
- ~~**F113 文件上传防护**~~：🟢 verified_at: 2026-05-17, method: curl multi-cases (MIME/magic/size/empty)
- ~~**F114 请求体大小限制**~~：🟢 verified_at: 2026-05-17, method: curl + 60MB body → 413
- **F115 LLM API 重试与熔断**：无指数退避重试和熔断器（`tenacity`/`pybreaker`）
- ~~**F116 优雅关闭（Graceful Shutdown）**~~：🟢 verified_at: 2026-05-18, method: SIGTERM + stream completion smoke test

### 中优先级（影响稳定性/可维护性）
- **F117 异步任务队列**：PDF 入库仍同步阻塞（Celery 已有框架但未接入主入库流程）
- **F079 对话分支功能**（上节标 🔴，代码完全不存在）
- **F038 WebSocket 进度推送**（上节标 🔴，WebSocket 完全不存在，当前为 Redis + HTTP 轮询）
- **F073 PostgreSQL 索引补齐**（conversations 表缺 user_id 索引）
- **F118 Embedding 批处理**（当前逐条 encode，入库速度瓶颈）

### 低优先级（长期规划）
- Kubernetes 部署（Helm Chart）
- 后端 CI/CD（GitHub Actions）
- API 版本管理（/api/v1/）
- 分页一致性（统一游标分页）
- 各路线图节点扩展功能

---

## 九、统计摘要

| 分类 | 数量 |
|------|------|
| 🟢 已实现 | 53（含 F020 升级） |
| 🟡 部分实现 | 17（含 F020 移出后） |
| 🔴 未实现（声称已实现但代码不存在） | 5 |
| 🔴 未实现（README 标 `[ ]` 的高/中优先级合规功能） | 8（F073、F113-F118、F119） |
| ⚫ 外网依赖描述点（含于 🟡，非独立条目） | 5 |

**声称已实现但实际未实现的高风险条目（需立即修正 README）**：
1. F038：WebSocket 导入进度（代码完全不存在，当前为 HTTP 轮询）
2. F031-pc：PC 端用户上传图片提问（前端 query 页面无图片上传 UI）
3. F107：零结果查询监控 API（端点不存在，数据也未采集）
4. F110：图谱快照 URL 分享（功能不存在）
5. F079：对话分支（功能不存在）

---

## 附录：五条抽样审核完整证据链（2026-05-17）

> 本节记录正式报告发布后、第一轮审核确认阶段对 5 条条目的深度验证过程。
> 证据链完整保留，供后续追溯。

---

### 抽样 1：F005 🟡 PDF 批量导入，断点续传

**验证命令及原始命中：**

```bash
# 查看 batch_ingest.py 完整内容（关键段摘录）
PROGRESS_FILE = Path("ingest_progress.json")

def load_progress() -> dict:
    if PROGRESS_FILE.exists():
        return json.loads(PROGRESS_FILE.read_text())
    return {"completed": [], "failed": {}}

def save_progress(p: dict) -> None:
    PROGRESS_FILE.write_text(json.dumps(p, ensure_ascii=False, indent=2))
    
# 每个文件成功后：progress["completed"].append(file_key) → save_progress(progress)

# grep resume/checkpoint：
backend/src/routers/docs/backfill.py:34: @router.post("/documents/backfill/resume")
backend/src/routers/admin_api/batch_ingest.py:27: @router.post("/resume")
backend/src/services/ingestion/batch_ingest_service.py:165: def resume_batch()
```

**行为分析：**
- 脚本层：每文件成功后立即写 `ingest_progress.json`（文件名级 checkpoint），崩溃重启后跳过已完成文件，最多重跑当前中断文件（MERGE 幂等）
- Admin API 层：Redis flag `K_BATCH_PAUSE` 实现运行时 pause/resume，跨重启需 Redis 持久化
- HTTP byte-range：全库无 Content-Range 实现

**最终判定：🟡 维持（脚本有文件级断点续传；Admin API 层跨重启能力受限；HTTP 分块未实现）**

---

### 抽样 2：F020 🟡→🟢 LangGraph 多跳推理 Agent

**验证命令及原始命中：**

```bash
grep -rn "from langgraph|import langgraph|langgraph" \
  backend/ --include="*.py" --include="*.toml" --include="*.txt"

backend/pyproject.toml:18:    "langgraph>=0.2.0",
backend/requirements.txt:21:langgraph==1.1.2
backend/src/services/retrieval/multi_hop.py:7:    from langgraph.graph import StateGraph, END
backend/src/services/retrieval/multi_hop.py:96:        raise RuntimeError("langgraph 未安装，无法执行 multi_hop 策略")
```

**StateGraph 真实构建（multi_hop.py 摘录）：**

```python
graph = StateGraph(AgentState)
graph.add_node("decompose",  decompose_question)
graph.add_node("retrieve",   retrieve)
graph.add_node("synthesize", synthesize_answer)
graph.set_entry_point("decompose")
graph.add_edge("decompose", "retrieve")
graph.add_conditional_edges(
    "retrieve",
    should_continue,
    {"retrieve": "retrieve", "synthesize": "synthesize"},
)
graph.add_edge("synthesize", END)
return graph.compile()
```

有条件边（`should_continue` 检查 `hop_count >= MAX_HOPS`），有迭代上限，有步骤记录。

**最终判定：🟢 升级（一审 grep 未覆盖 requirements.txt 导致漏判，深度验证后确认 LangGraph 真实使用）**

---

### 抽样 3：F038 🔴 WebSocket 导入进度推送

**验证命令及原始命中：**

```bash
grep -rn "WebSocket|websocket" \
  backend/src/ frontend/src/ \
  --include="*.py" --include="*.ts" --include="*.tsx"
→ 0 条命中（exit code 0）

grep -rn "send_json|send_text|send_bytes|\.send(" \
  backend/src/ --include="*.py"
→ 0 条命中
```

**实际进度机制（processing_tracker.py 读取）：**
- 状态写入 Redis（`processing:task:{task_id}`，TTL 86400s）
- 前端通过 HTTP GET 轮询读取
- 无任何 push / emit 机制

**最终判定：🔴 坐实（WebSocket 在 src 层零命中；当前实现为 Redis 存储 + HTTP 轮询；README [x] 属虚标）**

---

### 抽样 4：F107 🔴 零结果查询监控

**验证命令及原始命中：**

```bash
# analytics.py 完整端点枚举
grep -n "@router\." backend/src/routers/admin_api/analytics.py

analytics.py:25:  @router.get("/llm-costs")
analytics.py:105: @router.get("/analytics/hot-nodes")
analytics.py:188: @router.get("/analytics/strategy-stats")
# 共 3 个端点，无 /analytics/empty-queries

# LLMUsage / QueryFeedback schema
grep -n "zero|empty|no_result|sources_count" backend/src/db/models.py → 0 条

# stream.py 零结果记录
grep -n "zero|empty.*source|len.*source.*0" backend/src/routers/query/stream.py → 0 条
```

**结论：端点不存在，数据也未采集（LLMUsage 无 sources_count 字段，QueryFeedback 的 sources JSON 无零结果标记逻辑）。**

**最终判定：🔴 坐实，且从低优先级调整为中优先级（数据采集和端点均需补实现）**

---

### 抽样 5：F094 🟢 图神经网络（GNN/GraphSAGE）检索

**验证命令及原始命中：**

```bash
# gnn_service.py：完整实现，无 NotImplementedError / pass 占位
# 关键方法：_try_load(), search(), reload(), get_status()

# train_gnn.py 头部依赖：
import torch
import torch.nn.functional as F
from torch.optim import Adam
from backend.src.models.graphsage import GraphSAGE

# 模型权重文件：
ls -la backend/models/gnn/
  embeddings.npy   602 KB  (2026-04-08)
  chunk_ids.json   2.2 KB
  metadata.json    206 B
  model_best.pt    8.1 MB

# metadata.json 内容：
{
  "trained_at": 1775604874,
  "num_nodes": 147,
  "num_edges": 218,
  "num_pairs": 411,
  "feat_dim": 1040,
  "hidden_dim": 512,
  "out_dim": 1024,
  "best_loss": 2.7832865715026855,
  "epochs_run": 100
}

# gnn.py 端点注册：
@router.get("/status")   # /api/gnn/status
@router.post("/train")   # /api/gnn/train
@router.post("/refresh") # /api/gnn/refresh
```

**curl 烟雾测试：** 服务器本地未启动（CONNECTION_REFUSED），无法直接测试。
但权重文件存在（100 epoch / 147 节点训练完成），服务代码无占位，判定不受影响。

**最终判定：🟢 坚守（代码完整 + 权重已训练；服务器未运行为环境问题，非功能缺失）**

---

### 抽样审核统计校验结论

| 问题 | 原报告 | 修正后 |
|------|--------|--------|
| 总功能数 | 96 | ~97 |
| F020 状态 | 🟡 | 🟢（升级） |
| ⚫ 外网依赖数 | 13 | 5 个描述点 |
| F038 WebSocket | 🔴（待确认） | 🔴（坐实，HTTP 轮询） |
| F107 零结果监控 | 🔴（待确认） | 🔴（坐实，数据未采集） |
| F094 GNN | 🟢（待确认） | 🟢（坐实，权重已训练） |
| 第八节 8 条合规功能 | 无编号 | F073、F113-F118、F119 |

---

## 附录二：已知的预存在不一致（待决策，不在本轮处理）

审计 / 开发过程中发现的不影响当前功能、但代表潜在工程债务的发现。

### DB 字段反向 gap（2026-05-17 发现）

- **表**：`query_feedback`
- **DB 中存在的列**：`source_doc_id TEXT NOT NULL DEFAULT ''`
- **ORM 模型**（`src/routers/feedback.py`）：未声明此字段
- **影响**：ORM 读写 `QueryFeedback` 时该列被忽略，始终保持 `DEFAULT ''`，不会报错但数据永远不会被应用层写入或读取
- **待决策**：是补 ORM 字段（`source_doc_id: Mapped[str] = mapped_column(Text, default="")`），还是 `DROP COLUMN`（若已确认废弃）
