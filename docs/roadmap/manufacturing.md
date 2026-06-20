# 企业级智能制造技术扩展

> 本章面向航空制造企业的纵深落地场景，从工业互联、MLOps、实时流处理、多模态感知、安全合规等维度，规划系统从"知识库问答"向"制造智能中枢"的升级路径。

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

- [ ] **ERP（SAP PP/MM）**：查询工艺规范时，同步获取 SAP 中该零件的当前库存、替代件信息，纳入 LLM 上下文
- [ ] **MES 工单关联**：将生产工单（Work Order）与对应工艺规范章节绑定，操作工扫码工单时 MES 自动推送相关规范摘要
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

- [x] 集成 **PaddleOCR 3.0**（多语言 OCR，支持中文工程图纸）；扫描页自动检测并路由到 OCR 解析器
- [x] 版面分析（Layout Analysis）：PP-Structure 识别页面中的"正文/表格/图示"区域，分别用不同解析策略处理
- [x] **表格提取**：PP-Structure 表格区域 → HTML 解析 → 参数/值/单位列识别 → 写入 `Constraint` 节点（`source='table'`）

**工程图纸理解（Technical Drawing AI）**

- [x] 集成多模态 LLM（Qwen-VL / InternVL2）对机械工程图纸进行语义理解：提取零件编号、公差标注、装配关系
- [x] 将图纸中识别的约束（如"孔径 φ12 +0.02/-0.01 mm"）自动写入 `Constraint` 节点，关联对应 `Section`
- [x] 前端文档详情页：图纸缩略图可点击展开，AI 自动标注关键尺寸和公差带

**视觉质量检测（Visual QC AI）**

- [x] 集成 **YOLOv11**（ultralytics>=8.2）用于工件缺陷检测（划痕、裂纹、孔位偏差等），VLM 作为无权重 fallback
- [x] 检测到缺陷时，自动查询知识图谱中的 Hazard 节点，返回整改建议（`GET /api/qc/hazards/{defect_type}`）
- [x] 缺陷写入图谱 `Defect` 节点，通过 `DETECTED_IN→Image`、`RELATED_TO→Process` 关联，积累缺陷模式知识库

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
| 多模态 | 本地 Qwen2-VL / InternVL2 / MLX-VLM 图片理解 · 图文关联查询 | ✅ |
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
