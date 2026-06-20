# AI 生态扩展规划

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

- [ ] **系统提示缓存**：当前每次查询都重复发送约 800 token 的系统提示（角色定义 + 输出格式要求），启用 `cache_control: {"type": "ephemeral"}` 后缓存命中时费用接近零
- [ ] **长文档上下文缓存**：当同一章节被多次不同问题引用时，缓存该章节的 token 表示，避免重复编码（适用于热点章节）
- [ ] **Few-shot 示例缓存**：将固定的 few-shot 示例（实体提取、答案格式）写入缓存前缀，所有请求共享缓存
- [ ] **费用追踪区分**：在 `llm_usage` 表新增 `cache_read_tokens` / `cache_write_tokens` 字段，在成本报表中单独展示缓存节省金额

---

### 六、RAG 评估框架（RAGAS / TruLens）

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

- [x] 集成 `gptcache` 库或基于现有 Milvus 自行实现向量缓存层
- [x] 相似度阈值可在管理后台配置（默认 0.95）
- [x] 缓存 TTL 默认 24 小时，文档更新时按 `doc_id` 批量失效相关缓存条目
- [x] 命中统计写入 `cache_hits` 表，在成本报表中显示缓存节省的 token 数和费用

---

### 八、知识蒸馏与微调管线

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

### 九、先进 RAG 策略演进

当前系统已实现 Parallel / Sequential / Graph-Augmented / Multi-hop / GNN / Counterfactual 六种策略，以下为下一代检索增强技术方向。

**HyDE（假设文档嵌入）**

- [x] 在 `parallel.py` 中添加 `hyde=True` 开关，生成假设文档后与原始问题向量做加权平均再检索
- [ ] A/B 测试：对"定义型"问题（如"CPS1220 的技术要求"）HyDE 与标准向量的 Context Recall 对比

**Self-RAG（自省式检索）**

- [ ] 微调一个 Self-RAG 判别头（基于 Qwen2.5-7B），或以 Prompt 模拟四种反射 token 的语义
- [ ] 在 `stream.py` 中实现"生成→判断→按需检索→继续生成"的迭代循环
- [ ] 当模型判定检索内容不支持时，自动触发二次检索（扩大 top-k 或切换策略），记录回退次数至 Langfuse

**CRAG（纠错式 RAG）**

- [ ] 训练轻量级相关性评估器（cross-encoder）：若 top-1 相关性分数 < 0.4，触发 fallback
- [ ] Fallback 策略链：① 扩大 top-k → ② 切换全文检索 → ③ 调用外部 Bing/Tavily API 搜索公开航空标准
- [ ] 评估器分数写入每条 source 的 `relevance_score` 字段，前端来源卡片展示可信度条

**Adaptive RAG（自适应路由）**

- [x] 训练五分类 Prompt（或微调小模型）：`factual` / `procedural` / `comparative` / `constraint` / `hypothetical`
- [x] 路由规则：factual → parallel，procedural → sequential + graph，comparative → compare 策略，constraint → entity-aware，hypothetical → counterfactual
- [ ] 前端在 AI 气泡头部展示"自动选择策略：图增强"，用户可一键覆盖

**Microsoft GraphRAG（社区摘要式检索）**

- [ ] 使用 Neo4j GDS Louvain 算法对 Section 节点做社区检测，每个社区对应一个工艺主题簇
- [ ] 离线为每个社区生成 LLM 摘要，存入 `community_summaries` 表
- [ ] 问题路由：全局型问题 → 遍历社区摘要；局部型问题 → 现有向量/图检索
- [ ] `GET /api/graph/communities` 返回社区列表及其摘要，前端图谱以不同颜色区域渲染

**RAFT（检索增强微调）**

- [ ] 构造 RAFT 数据集：每条样本包含 1 个相关章节 + 3 个干扰章节 + 标准答案（含 `<citation>` 标注）
- [ ] 与标准 SFT 数据集分批训练，对比 Faithfulness 指标，验证抗干扰能力提升效果

**ColBERT / ColPali 晚交互检索**

- [ ] 集成 ColBERT v2：不对 query 和 document 编码为单一向量，而是逐 token 交互后取最大相似度，提升长文本精确匹配
- [ ] ColPali：直接对 PDF 页面图像编码（Vision-Language Model），无需文字提取即可检索图文混排技术文档

---

### 十、技术栈汇总（AI 生态）

| 类别 | 技术 | 作用 | 状态 |
|------|------|------|------|
| AI 协议 | MCP（Model Context Protocol） | 将知识库暴露为 AI 工具，供 Claude Desktop / Cursor 直接调用 | 规划中 |
| AI 协议 | A2A（Agent-to-Agent） | 与企业内网其他 AI Agent 互联互调 | 规划中 |
| Agent 框架 | LangGraph | 多跳推理 ReAct Agent，Tool Use 编排 | ✅ 已实现 |
| Agent 框架 | Agent Skills / Function Calling | 领域专用结构化工具集 | 规划中 |
| 提示优化 | DSPy | 自动优化实体提取、Text2Cypher、答案生成的 Prompt | 规划中 |
| 成本优化 | Prompt Caching | 系统提示和热点文档缓存复用，减少重复 token 处理 | 规划中 |
| 效果评估 | RAGAS | 自动评估 Faithfulness / Relevancy / Recall / Precision | 规划中 |
| 效果评估 | TruLens | 生产环境在线评分，异常问题自动入复核队列 | 规划中 |
| 响应加速 | 语义缓存（GPTCache） | 相似问题向量匹配命中缓存，< 50ms 响应 | ✅ 已完成 |
| 模型优化 | 知识蒸馏 + LoRA 微调 | 本地小模型替代远程 API，延迟和成本双降 | 规划中 |
| 图神经网络 | GraphSAGE GNN | 结构感知节点 Embedding，提升图结构相关章节召回 | ✅ 已实现 |
| 假设推理 | 反事实因果推理 | "如果去掉 X 步骤"类假设问题的图谱因果链模拟 | ✅ 已实现 |
| 可观测性 | Langfuse | LLM 调用链路追踪、Token 成本统计 | ✅ 已实现 |
