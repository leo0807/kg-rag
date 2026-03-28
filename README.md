# CPS 知识库 — 航空工艺规范 GraphRAG 系统

> 基于知识图谱与向量检索融合的航空制造工艺规范智能问答系统

![Tech Stack](https://img.shields.io/badge/Next.js-15-black)
![Tech Stack](https://img.shields.io/badge/FastAPI-0.115-green)
![Tech Stack](https://img.shields.io/badge/Neo4j-5.20-blue)
![Tech Stack](https://img.shields.io/badge/Python-3.12-yellow)

## 系统架构
```
PDF 文件
   ↓ ETL 解析（pdfplumber + 正则）
Neo4j 图谱 ←→ Milvus 向量库
   ↓ GraphRAG 四策略融合引擎
FastAPI 后端
   ↓ REST API
Next.js 前端
```

## 功能特性

**智能问答**
- 四种检索策略：并行检索（RRF融合）、串行检索、图谱增强、多跳推理
- 来源溯源：每条回答附带引用章节和相关度评分
- 会话管理：历史记录持久化到 Neo4j，支持新建和删除

**文档管理**
- PDF 批量导入，支持断点续传
- 自动解析文档编号、版本、章节结构、引用关系
- 防重复导入检测
- 章节内容展开和全文搜索高亮

**知识图谱可视化**
- D3.js 力导向图，展示文档间引用关系
- 节点/边类型过滤，缩放和重置
- 点击 Document 节点跳转文档详情

**工程特性**
- API 限流（查询 30次/分钟，导入 10次/分钟）
- 自托管 Langfuse LLMOps 可观测性
- Docker Compose 一键启动全栈
- 24 个单元/集成测试，0.61 秒全部通过

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Next.js 15 · TypeScript · Tailwind CSS · D3.js |
| 后端 | FastAPI 0.115 · Python 3.12 · Pydantic v2 |
| 图数据库 | Neo4j 5.20 |
| 向量数据库 | Milvus 2.4 |
| 缓存 | Redis 7 |
| 可观测性 | Langfuse 2（自托管） |
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

### 批量导入 PDF
```bash
cd backend
python scripts/batch_ingest.py --dir /path/to/pdf/folder --skip-existing
```

## 项目结构
```
kg-rag/
├── backend/
│   ├── src/
│   │   ├── main.py              # FastAPI 入口，限流中间件
│   │   ├── core/                # 配置、数据库、日志、可观测性
│   │   ├── routers/             # API 路由
│   │   │   ├── documents.py     # 文档库（分页+搜索）
│   │   │   ├── graph.py         # 图谱数据
│   │   │   ├── query.py         # 智能问答
│   │   │   └── sessions.py      # 会话管理
│   │   └── services/            # 业务逻辑
│   │       ├── parser.py        # PDF 解析
│   │       └── neo4j_writer.py  # 图谱写入
│   ├── scripts/
│   │   └── batch_ingest.py      # 批量导入脚本
│   └── tests/                   # 24 个测试
├── frontend/
│   └── src/
│       ├── app/
│       │   ├── ingest/          # 导入文件
│       │   ├── library/         # 文档库
│       │   ├── query/           # 智能问答
│       │   └── graph/           # 图谱可视化
│       ├── components/          # 公共组件
│       └── lib/api.ts           # 统一请求封装
└── docker-compose.yml
```

## 运行测试
```bash
cd backend
python -m pytest tests/ -v
```

## 未来计划

- [ ] BAAI/bge-m3 向量检索接入（模型下载中）
- [ ] LangGraph 多跳推理 Agent
- [ ] 浅色/深色主题切换
- [ ] AWS 云部署