# 航空工艺规范 GraphRAG 知识库

基于知识图谱与向量检索融合的航空制造工艺规范智能问答系统。

## 技术栈

**前端**
- Next.js 15 (App Router) · TypeScript 5 · Tailwind CSS
- D3.js 图谱可视化 · shadcn/ui

**后端**
- FastAPI 0.115 · Python 3.12 · Pydantic v2
- Neo4j 5.20 · Milvus 2.4 · Redis 7

**AI**
- GraphRAG 四策略融合引擎（串行 / 并行RRF / 图谱增强 / 多跳推理）
- LangGraph Agent 编排
- BAAI/bge-m3 本地 Embedding 模型

**工程**
- Docker Compose · GitHub Actions CI/CD
- Langfuse LLMOps 可观测性（自托管）
- pytest 单元测试

## 本地开发启动

### 前置条件
- Docker Desktop 已启动
- conda 已安装
- Node.js 18.18+

### 第一步：启动基础服务
```bash
docker compose up -d
```

启动后可访问：
- Neo4j Browser：http://localhost:7474 （用户名/密码：neo4j/aviation123）
- Milvus Attu：http://localhost:8080
- Langfuse：http://localhost:3001

### 第二步：启动后端
```bash
conda activate kg-rag
cd backend
python -m uvicorn src.main:app --reload --port 8000
```

API 文档：http://localhost:8000/docs

### 第三步：启动前端
```bash
cd frontend
npm run dev
```

访问：http://localhost:3000

## 项目结构
```
kg-rag/
├── backend/
│   ├── src/
│   │   ├── main.py              # FastAPI 入口
│   │   ├── core/                # 配置、数据库连接
│   │   ├── routers/             # API 路由
│   │   │   ├── documents.py     # 文档库接口
│   │   │   ├── graph.py         # 图谱接口
│   │   │   └── query.py         # 查询接口
│   │   ├── services/            # 业务逻辑
│   │   │   ├── parser.py        # PDF 解析
│   │   │   ├── neo4j_writer.py  # 图谱写入
│   │   │   └── graphrag_engine.py # RAG 引擎
│   │   └── models/              # Pydantic 模型
│   └── tests/                   # 单元测试
├── frontend/
│   └── src/
│       ├── app/                 # Next.js 页面
│       │   ├── ingest/          # 导入文件
│       │   ├── library/         # 文档库
│       │   ├── query/           # 智能问答
│       │   └── graph/           # 图谱可视化
│       ├── components/          # 公共组件
│       └── lib/                 # 工具函数
└── docker-compose.yml           # 基础设施
```

## 运行测试
```bash
cd backend
python -m pytest tests/ -v
```

## 功能说明

| 功能 | 说明 |
|------|------|
| PDF 导入 | 拖拽上传，自动解析元数据、章节结构、引用关系 |
| 文档库 | 查看所有已入库规范，支持点击查看章节目录 |
| 智能问答 | 四种检索策略，返回答案 + 来源章节溯源 |
| 图谱可视化 | D3 力导向图，展示文档间引用关系 |
| 查询历史 | 本地保存最近 10 条查询记录 |

## 未来计划
- [ ] 浅色/深色主题切换（需重构 CSS 变量系统）
- [ ] Embedding 向量检索接入（模型下载中）
- [ ] AWS 云部署