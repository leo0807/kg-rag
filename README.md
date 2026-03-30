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

访问 http://localhost:3000，注册账号后开始使用。

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
- [ ] 浅色/深色主题切换
- [ ] 移动端适配
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
- [ ] Tool / Material / Process 节点间关系：`COMPATIBLE_WITH`、`REQUIRES_TOOL`（Process→Tool）、`ALTERNATIVE_TO`（材料替代关系）
- [ ] 文档版本溯源：`SUPERSEDES` / `OBSOLETED_BY` 关系，支持"本次变更了哪些章节"查询
- [ ] 工艺约束节点：力矩值、公差、温度等结构化参数从正文提取，形成独立节点并与章节关联
- [ ] 跨文档语义边：相似章节间自动建立 `SIMILAR_TO` 关系（基于向量余弦相似度阈值）
- [ ] 图谱统计 API：`GET /api/stats/knowledge-graph` 返回各类节点数量、边数量、覆盖率

**图谱可视化**
- [ ] 图谱节点数量限制可配置（当前 Document:50 / Section:200 / Image:100 均硬编码）
- [ ] Tool / Material / Process 节点加入可视化及过滤（实体已写入 Neo4j，前端尚未渲染）
- [ ] 节点详情侧边栏：点击任意节点展开属性面板，而非仅 tooltip
- [ ] 图谱导出：支持导出为 JSON/GraphML，供 Gephi 等工具进一步分析
- [ ] 支持按文档 `doc_id` 筛选，只展示单个规范的子图

**实体质量**
- [ ] 实体去重与归一化：当前用名称 MERGE，"液压泵" 与 "液压系统泵" 会产生冗余节点，需同义词合并
- [ ] 实体审核页面：管理员可以查看、合并、删除自动提取的 Tool/Material/Process 节点

---

### 检索与推理增强

**查询策略**
- [ ] 实体感知检索：查询时提取问题中的工具/材料名，优先召回含对应 `REQUIRES_TOOL` / `USES_MATERIAL` 边的章节
- [ ] 自动策略选择：根据问题类型（定义型/步骤型/对比型/约束型）自动选择检索策略，无需用户手选
- [ ] 图谱增强策略延伸 Tool/Material/Process：当前 `graph_augmented` 仅展开 `HAS_SUBSECTION` / `NEXT_SECTION`，未利用实体节点跨章节扩展
- [ ] 跨文档推理：沿 `REFERENCES` 边追踪被引用规范，将其相关章节纳入上下文

**Reranker**
- [ ] Reranker 统一应用：当前 `sequential` 策略未经过精排，导致结果质量低于 `parallel`
- [ ] Reranker 内容截断优化：当前截断到 512 字符，改为按 token 截断，减少信息损失

**多跳推理**
- [ ] 多跳推理迭代上限保护：当前 `multi_hop.py` 无最大迭代次数限制，存在死循环风险
- [ ] 多跳中间步骤可见化：前端展示推理链路（子问题 → 召回章节 → 子答案）

---

### 数据质量与一致性

- [ ] 同步端点补齐：`POST /api/query`（同步）缺少 `history` 和 `images` 参数，与流式端点不一致
- [ ] Session vs Conversation 统一：存在 Neo4j `QuerySession` 与 PostgreSQL `Conversation` 两套历史存储，需合并或明确分工
- [ ] Section 节点冗余字段清理：`section_number` 与 `number` 字段重复存储（`neo4j_writer.py:65-66`）
- [ ] 图片分析结果缓存：重复入库相同图片时跳过 VLM 调用，避免浪费 API 额度

---

### 实体与文档 API

- [ ] `GET /api/documents/{doc_id}/entities` — 列出文档中所有工具/材料/工序节点
- [ ] `GET /api/entities?type=Tool&q=扳手` — 实体搜索与过滤
- [ ] `GET /api/documents/{doc_id}/images` — 列出文档图片及 VLM 描述
- [ ] `POST /api/documents/{doc_id}/reanalyze` — 对已入库文档重新提取实体/图片（用于模型升级后）
- [ ] `GET /api/query/suggest?q=...` — 基于知识图谱的查询建议/自动补全

---

### 工程基础设施

- [ ] 配置文件去重：`config.py` 中 `MILVUS_HOST`、`REDIS_URL`、`LLM_API_URL` 等存在重复定义，后者覆盖前者
- [ ] PostgreSQL 索引补齐：`conversations` 表缺 `user_id` 索引，`query_feedback` 表无任何索引
- [ ] Neo4j 全文索引验证：启动时检查 `cps_fulltext_index` 是否存在，不存在则自动创建
- [ ] GPU 支持：Embedder 硬编码 `device="cpu"`，需检测 CUDA 并自动切换
- [ ] 配置热重载：修改模型/策略配置后无需重启服务

---

### 前端与用户体验

- [ ] 文档对比页差异算法：当前用字符串相等判断差异，改为 Myers diff 算法，支持词级高亮
- [ ] 浅色 / 深色主题切换
- [ ] 移动端适配
- [ ] 知识图谱节点搜索框：在图谱页输入节点名称快速定位并高亮
- [ ] 对话分支：支持从某条 AI 消息处新开分支，探索不同追问路径

---

### 测试覆盖

- [ ] 实体提取单元测试（`entity_extractor.py` / `entity_writer.py`）
- [ ] 检索策略集成测试（parallel / sequential / graph_augmented / multi_hop）
- [ ] Reranker 效果回归测试（保证精排结果质量）
- [ ] 多轮对话端到端测试
- [ ] 流式 SSE 响应测试
- [ ] 鉴权边界测试（未登录/无权限访问受保护接口）
