# 民用航空制造业 GraphRAG 系统

基于知识图谱（Neo4j）与向量检索（Milvus）融合的航空技术智能问答系统。

## 项目结构

```
kg-rag/
├── docker-compose.yml            # 本地开发环境（Neo4j + Milvus）
├── requirements.txt              # Python 依赖
├── .env                          # API Key 等敏感配置（不提交 git）
├── README.md
│
├── scripts/                      # 一次性执行的初始化 / 数据导入脚本
│   ├── verify_connections.py     # 验证数据库连通性
│   ├── init_graph_schema.py      # 建索引、约束、写入初始图谱数据
│   └── ingest_pdf.py             # PDF 解析 → 实体抽取 → 写入知识库
│
├── aviation_graphrag/            # 核心业务代码（可被导入的包）
│   ├── config/
│   │   └── settings.py           # 全局配置（数据库地址、模型参数等）
│   ├── core/
│   │   └── models.py             # 数据模型（GraphNode、VectorChunk 等）
│   ├── retrievers/
│   │   ├── graph_retriever.py    # Neo4j 图谱检索器
│   │   └── vector_retriever.py   # Milvus 向量检索器
│   ├── fusion/
│   │   └── engine.py             # GraphRAG 融合引擎（四种策略）
│   ├── llm/
│   │   └── client.py             # LLM 客户端（Qwen / DeepSeek）
│   └── main.py                   # FastAPI 服务入口
│
└── tests/
    ├── test_graph_retriever.py
    └── test_vector_retriever.py
```

## 系统架构

```
用户问题
   │
   ▼
实体识别（LLM）
   │
   ├──────────────────────┐
   ▼                      ▼
Neo4j 图谱检索         Milvus 向量检索
子图 / 多跳推理        语义相似文档
   │                      │
   └──────────┬───────────┘
              ▼
         融合 + 重排（RRF）
              │
              ▼
         LLM 生成答案
              │
              ▼
         答案 + 溯源来源
```

## 四种融合策略

| 策略 | 适用场景 |
|------|----------|
| `sequential`       | 精确实体已知，需要文档深度支撑 |
| `parallel`         | 宽泛问题，兼顾结构化和非结构化信息 |
| `graph_augmented`  | 实体关系推理 + 精确文档定位 |
| `multi_hop`        | 复杂排故、根因分析、合规影响评估 |

## 快速开始

### 1. 启动数据库

```bash
docker compose up -d
```

访问：
- Neo4j Browser：http://localhost:7474（账号 neo4j / aviation123）
- Milvus 管理界面：http://localhost:8080

### 2. 创建 Python 环境

```bash
conda create -n aviation-graphrag python=3.11 -y
conda activate aviation-graphrag
pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入 API Key
```

### 4. 初始化图谱

```bash
python scripts/verify_connections.py   # 验证数据库连通
python scripts/init_graph_schema.py    # 初始化图谱结构
```

### 5. 导入 PDF 数据

```bash
python scripts/ingest_pdf.py --file 你的文档.pdf
```

### 6. 启动服务

```bash
uvicorn aviation_graphrag.main:app --reload --port 8000
```

### 7. 查询示例

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "C919液压系统作动筒内泄如何排查？",
    "strategy": "multi_hop"
  }'
```

## 环境变量说明

新建 `.env` 文件，填入以下内容：

```
# 国产大模型（二选一）
DASHSCOPE_API_KEY=sk-xxx        # 阿里云 Qwen
# DEEPSEEK_API_KEY=sk-xxx       # DeepSeek

# 数据库（本地开发默认值，一般不需要改）
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=aviation123
MILVUS_HOST=localhost
MILVUS_PORT=19530
```

## 开发进度

- [x] 阶段一：环境搭建
- [x] 阶段二：知识图谱建模
- [ ] 阶段三：RAG 流水线
- [ ] 阶段四：GraphRAG 融合引擎
- [ ] 阶段五：ETL 数据管道
- [ ] 阶段六：API 服务 + 前端


数据层 — 民航制造业的数据来源通常包括 AMM/CMM 技术手册（PDF/XML格式）、适航指令（FAA AD、EASA AD）、S1000D/ATA 标准文档、BOM 物料清单，以及 MRO 维修历史数据。需要重点考虑数据权限管控。
处理层（ETL） — 核心挑战在于航空文档的专业术语识别，建议使用 spaCy + 航空领域微调模型进行命名实体识别（NER），提取零件号、系统代码、故障模式等关键实体，再用规则或小型 LLM 进行关系抽取。
存储层 — 图数据库（Neo4j）负责存储结构化的实体关系，如"零件 → 所属系统 → 飞机型号"、"故障模式 → 可能原因 → 维修措施"。向量数据库（Chroma 或 Weaviate）存储文档片段的语义嵌入，支持自然语言检索。两者并行运行，各司其职。
融合层（GraphRAG 核心） — 这是整个系统的关键。用户查询时，同时触发图谱的结构化子图检索和向量的语义检索，然后将两路结果合并后送入 LLM 生成最终答案，并附上溯源依据。
应用层 — 优先实现的场景：技术排故问答、适航合规核查、零件影响域分析（一个零件失效会影响哪些系统）。
## 本地开发启动
```bash
# 后端
conda activate kg-rag
cd backend
python -m uvicorn src.main:app --reload --port 8000
```
