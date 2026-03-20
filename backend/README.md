# 航空工艺规范 GraphRAG 知识库 — Backend

基于 **Neo4j 知识图谱 + 本地大模型** 的 RAG 系统，专为航空工艺规范（CPS 系列）设计。

## 技术栈

| 组件 | 选型 |
|------|------|
| Web 框架 | FastAPI |
| 图数据库 | Neo4j 5.x |
| Embedding 模型 | BAAI/bge-m3（本地，1024 维） |
| LLM | Ollama（默认 qwen2.5:7b，可配置） |
| 包管理 | uv |

## 知识图谱结构

```
Document
  ├─ HAS_SECTION ──► Section
  │                    ├─ HAS_SUBSECTION ──► Section（子章节）
  │                    └─ NEXT_SECTION   ──► Section（相邻章节）
  └─ REFERENCES  ──► Document（引用的其他规范）
```

**节点属性**

- `Document`：`name`（规范编号）、`title`、`version`、`issue_date`、`doc_type`
- `Section`：`chunk_id`、`number`、`title`、`content`、`embedding`（1024 维向量）

**Neo4j 索引**

- `document_name`：唯一性约束，加速 MERGE
- `section_chunk_id`：唯一性约束，加速 MERGE
- `section_embedding`：向量索引（cosine，1024 维），支持 ANN 搜索

## 快速开始

### 1. 环境准备

```bash
# 安装依赖
cd backend
uv sync

# 启动 Neo4j（需要 Neo4j 5.x，支持向量索引）
# 启动 Ollama 并拉取模型
ollama serve
ollama pull qwen2.5:7b
```

### 2. 配置

在项目根目录创建 `.env`：

```env
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password

OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b   # 可换成其他已拉取的模型

RETRIEVER_TOP_K=5          # 向量召回数量
```

### 3. 启动服务

```bash
cd backend
uv run uvicorn src.main:app --reload
```

访问 `http://localhost:8000/docs` 查看交互式 API 文档。

## API 说明

### `GET /api/health`
健康检查。

### `GET /api/stats`
返回 Neo4j 中的节点总数。

### `POST /api/preview`
解析 PDF 并返回结构化预览，**不写入图谱**。适合调试解析效果。

**请求**：`multipart/form-data`，字段名 `file`，上传 PDF。

### `POST /api/ingest`
解析 PDF 并完整写入知识图谱，包括：
- Document 节点和 Section 节点
- HAS_SECTION / HAS_SUBSECTION / NEXT_SECTION / REFERENCES 关系
- 每个 Section 的 bge-m3 向量

**请求**：`multipart/form-data`，字段名 `file`，上传 PDF。

```json
// 响应示例
{ "status": "OK", "doc_id": "CPS1234", "sections": 42 }
```

### `POST /api/query`
知识图谱 RAG 查询，返回 LLM 生成的答案和引用章节。

```json
// 请求
{ "question": "铝合金零件阳极氧化处理的温度要求是什么？" }

// 响应
{
  "answer": "根据 § 3.2.1，阳极氧化处理温度应控制在 18～22°C ...",
  "sources": [
    { "chunk_id": "CPS1234_3.2.1", "doc_id": "CPS1234",
      "number": "3.2.1", "title": "温度控制", "score": 0.9231 }
  ]
}
```

**RAG 流程**

1. 用 bge-m3 将问题向量化
2. 在 Neo4j 向量索引中召回 top-K 最相关 Section
3. 通过图遍历获取每个命中节点的父章节（大纲上下文）和相邻章节（防止内容截断）
4. 将拼装好的上下文发给 Ollama 生成答案

## 项目结构

```
backend/
├── src/
│   ├── core/
│   │   ├── config.py       # 配置（env 变量）
│   │   └── database.py     # Neo4j 连接 + schema 初始化
│   ├── models/
│   │   └── schemas.py      # Pydantic 数据模型
│   ├── routers/
│   │   └── query.py        # /api/query 端点
│   └── services/
│       ├── parser.py       # PDF 解析（元数据 + 章节切分）
│       ├── neo4j_writer.py # 图谱写入
│       ├── embedder.py     # bge-m3 向量化（单例）
│       ├── retriever.py    # 向量召回 + 图谱增强
│       └── llm.py          # Ollama 调用封装
└── pyproject.toml
```
