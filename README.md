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
