# 智能知识图谱演进路线图

> 当前图谱已实现：7 种节点类型 · 18 种关系类型 · 力导向可视化 · 图增强检索 · 多跳推理
> 以下为面向航空制造领域的深度图智能能力扩展规划，从数据建模到 AI 推理全面覆盖。

---

### 一、图谱结构扩展：更丰富的知识表示

**新节点类型**
- [ ] **Standard（标准规范节点）**：将 GJB、AS9100、HB、MIL-SPEC 等外部标准写入图谱，与 Document 建立 `COMPLIES_WITH` / `REFERENCED_BY` 关系，支持合规性追踪
- [ ] **Component（零件节点）**：从工艺规范中提取零件编号（如 P/N、件号），建立 `(Section)-[:APPLIES_TO]->(Component)` 关系，支持按零件查询所有相关工艺
- [ ] **Person / Role（人员角色节点）**：文档编制者、审核者、批准者，`(Document)-[:AUTHORED_BY]->(Person)`，支持追溯文档责任链
- [ ] **Equipment（设备/工装节点）**：区别于 Tool（手工工具），Equipment 指专用工装夹具、检测设备（如扭矩扳手校准仪），`(Section)-[:REQUIRES_EQUIPMENT]->(Equipment)`
- [ ] **Step（工序步骤节点）**：将 Section 中的有序步骤拆解为独立节点，`(Section)-[:HAS_STEP {order}]->(Step)-[:NEXT_STEP]->(Step)`，支持步骤级检索与重排
- [ ] **Hazard（危险源节点）**：从安全警告中提取危险源（如高压液压油喷射风险），`(Section)-[:WARNS_OF]->(Hazard)`，构建安全知识子图
- [ ] **Inspection（检验节点）**：提取质量检验要求，`(Section)-[:REQUIRES_INSPECTION]->(Inspection {method, frequency, acceptance_criteria})`
- [ ] **ChangeRecord（变更记录节点）**：每次文档版本更新时创建，存储变更原因、审批人、生效日期，`(Document)-[:HAS_CHANGE_RECORD]->(ChangeRecord)`

**新关系类型**
- [ ] **`PRECEDES` / `FOLLOWS`（工序先后）**：跨章节的工序依赖关系，如"液压测试必须在管路安装后进行"，支持工艺流程的拓扑排序
- [ ] **`CONFLICTS_WITH`（冲突检测）**：自动识别同一零件在不同文档中出现矛盾的工艺要求（如力矩值不一致），建立冲突边并告警
- [ ] **`DERIVED_FROM`（知识溯源）**：当某工艺节点由另一基础规范推导而来时，建立溯源关系，支持"为什么要这样做"的深层追问
- [ ] **`VALIDATED_BY`（验证关系）**：将工艺参数（Constraint）与试验报告或验证记录关联，`(Constraint)-[:VALIDATED_BY]->(Document {type: "test_report"})`
- [ ] **`SUPERSEDES_SECTION`（章节级版本替换）**：粒度比文档级 `SUPERSEDES` 更细，精确到哪个章节被哪个新章节替代

---

### 二、图算法与智能分析

**图拓扑分析**
- [ ] **PageRank 重要性排序**：对 Section 节点运行 PageRank（被引用次数多的章节权重高），检索时将 PageRank 分数融入 RRF 排名，提升核心工艺章节的召回优先级
- [ ] **社区检测（Louvain / LPA）**：使用 Neo4j GDS 对节点进行社区发现，识别高度相关的工艺簇（如"液压系统相关章节集合"），用于自动生成工艺主题标签
- [ ] **中心性分析（Betweenness Centrality）**：找出图谱中的"桥接节点"（连接不同工艺领域的关键章节），高中心性节点可能是跨专业知识的核心交汇点
- [ ] **最短路径查询**：`GET /api/graph/path?from=doc_id_A&to=doc_id_B` 返回两文档/章节之间的知识关联路径，解释为什么两份规范相互关联
- [ ] **子图相似度**：当导入新文档时，自动计算与已有文档的子图结构相似度（GED / WL kernel），识别重复或高度相似的工艺规范
- [ ] **知识覆盖度热力图**：对图谱进行密度分析，识别哪些零件类型、工艺领域的知识节点稀疏（知识盲区），输出覆盖度报告

**推理与问题检测**
- [ ] **约束冲突检测引擎**：自动比对同一 Component 上来自不同 Document 的 Constraint 节点，若力矩范围、温度限值有交叉矛盾则生成告警，`POST /api/graph/conflict-check?component=`
- [ ] **工艺完整性校验**：检测工序图中的孤立节点（有 Section 但无 Tool / Material / Process 关联），生成"实体提取不完整"报告，辅助数据质量改进
- [ ] **悬空引用检测**：扫描所有 `REFERENCES` 边，若目标文档不在图谱中则标记为悬空引用，提示管理员补充入库
- [ ] **循环依赖检测**：检测工序先后关系（`PRECEDES`）中是否存在环路（A→B→C→A），防止工艺流程逻辑错误
- [ ] **版本一致性检查**：检测同一设备型号下，不同版本文档之间 Constraint 值的漂移趋势，自动生成版本对比报告

---

### 三、图增强检索：从语义到结构的融合

**检索策略升级**
- [x] **图神经网络（GNN）检索**：训练 GraphSAGE 模型，将节点结构特征（邻居类型分布、关系密度）融入节点 Embedding，替代纯文本向量，提升结构相似节点的检索精度
- [ ] **个性化 PageRank（PPR）检索**：以用户查询锚定的初始节点为种子，运行个性化 PageRank，按随机游走概率排序候选节点，替代当前固定深度的 BFS 扩展
- [ ] **关系路径感知检索**：将"两节点之间通过哪种路径连接"作为语义特征，区分"直接相关"（共享 Tool）与"间接相关"（共享 Material 再共享 Process），差异化加权
- [ ] **时序感知检索**：查询时默认优先返回最新版本文档的章节，过期章节降权（基于 `SUPERSEDES` 关系链的版本时序）
- [ ] **对比检索模式**：`strategy=compare` 新策略，自动并行检索两份文档的相同主题章节，输出结构化对比结果（差异项、共同点、冲突点）
- [ ] **约束感知检索**：检测问题中是否含数值（如"液压压力 3000 PSI"），若有则优先召回 Constraint.value 范围覆盖该数值的章节

**上下文图构建**
- [ ] **动态子图提取**：回答问题时不仅返回相关 Section，同时提取以这些节点为中心的 2 跳子图（包含 Tool、Material、Constraint），将子图结构序列化为 LLM 上下文的结构化补充
- [ ] **推理链图谱化**：将多跳推理过程（子问题→节点→边→子答案）以图结构记录并存入 Neo4j，支持后续查询"这个答案是如何推理得出的"
- [x] **反事实图查询**：支持"如果去掉 X 工序，Y 零件还能满足 Z 要求吗？"类型的假设推理，通过图谱中的约束路径模拟因果链

---

### 四、时序与版本智能

- [x] **版本时间线视图**：前端新增 Timeline 视图，以横轴为时间、纵轴为文档，展示版本演进、章节变更、关系新增的历史序列
- [ ] **章节级 Diff 图谱**：对同一章节的两个版本，生成 Myers Diff 并将变更写入图谱（`CHANGED_TO` 边携带 diff patch 属性），支持"这个章节改了什么"的精确问答
- [x] **变更影响分析**：当一个 Document 更新版本时，自动沿 `REFERENCES` 关系扩散，找出所有引用该文档的下游规范，生成"受影响文档清单"，辅助变更管理
- [ ] **变更频率热力图**：统计各 Section 节点的历史变更次数（`ChangeRecord` 节点数量），在图谱上以热力色渲染，识别"高度易变"章节（可能存在工艺不成熟问题）
- [ ] **有效性时间窗口**：为 Document / Section 节点增加 `valid_from` / `valid_until` 属性，查询时自动过滤生效期外的节点（支持"查询某时间点有效的工艺规范"）
- [ ] **废止预警**：定期扫描 `OBSOLETED_BY` 关系，若系统内存在指向已废止文档的 `REFERENCES` 边，则触发告警通知文档管理员

---

### 五、领域本体与外部知识融合

- [ ] **航空领域本体对齐**：导入 ATA 100 章节码（飞机系统分类标准）作为顶层分类本体，将 Document / Section 节点映射至对应 ATA Chapter，支持按 ATA 章节号检索（如"ATA 29 液压系统所有相关规范"）
- [ ] **合规性矩阵**：构建规范 → 标准条款的映射图（如 GJB 241 §3.2.1 → 本系统某工艺章节），`GET /api/graph/compliance-matrix?standard=GJB241` 输出覆盖度矩阵，识别合规盲区
- [ ] **术语本体（Ontology）**：建立航空制造术语同义词表，统一"液压泵"/"液压驱动泵"/"液压系统泵"等变体，作为图谱实体归一化的权威词典
- [ ] **供应商知识图谱**：将材料供应商信息（`Supplier` 节点）接入，`(Material)-[:SUPPLIED_BY]->(Supplier {approval_status, lead_time})`，支持"这个材料有哪些合格供应商"
- [ ] **BOM（物料清单）集成**：从 ERP/PDM 系统导入 BOM 数据，将零件号（Part Number）节点与图谱中的 Component 节点对齐，实现工艺规范与制造清单的双向追溯
- [ ] **CAD 元数据关联**：从 STEP/IGES 文件中提取几何特征（材料、公差带、表面粗糙度），与图谱中的 Constraint 节点匹配，打通设计-工艺-制造数据孤岛

---

### 六、可视化与交互升级

**多视图模式**
- [ ] **层级树状图（Hierarchy View）**：Document → Section → Subsection 的树形折叠展开，适合快速浏览单个规范的章节结构，与力导向图互相切换
- [ ] **关系矩阵视图（Adjacency Matrix）**：行列均为 Document 节点，格子颜色编码 `REFERENCES` / `SIMILAR_TO` 关系强度，适合发现文档间的高频引用簇
- [ ] **桑基图（Sankey Diagram）**：展示从工艺流程（Process）→ 使用的工具（Tool）→ 消耗的材料（Material）→ 产生的约束（Constraint）的能量流向，直观呈现工艺链路
- [x] **时间线图（Timeline View）**：以版本号为 X 轴，文档为 Y 轴，节点变更事件为气泡，动态播放知识库演进历史
- [ ] **地理热力图**：若文档与工厂车间（Shop）关联，在厂区平面图上叠加工艺规范热力（哪个工位涉及最多规范），支持数字化车间场景

**交互能力**
- [ ] **图上直接编辑**：管理员在可视化界面中拖拽创建关系（如将两个 Tool 节点连上 `ALTERNATIVE_TO` 边），无需写 Cypher，操作自动同步至 Neo4j
- [ ] **Cypher 查询控制台**：专家用户可直接输入 Cypher 查询语句，结果实时渲染为交互图谱，支持图谱探索性分析
- [ ] **节点注释与标注**：用户可对任意节点添加注释（`Note` 节点），`(Section)-[:HAS_NOTE {author, created_at}]->(Note)`，团队协作标注知识盲点或疑问
- [ ] **图谱快照与分享**：将当前图谱视图（含过滤、高亮状态）保存为 URL 可分享的快照，团队成员打开链接可复现完全相同的视图状态
- [x] **增量渲染与虚拟化**：节点超过 1000 时切换为 WebGL（Three.js / PixiJS）渲染，维持交互帧率 > 30fps；超过 5000 时降级为 Canvas 静态热力图
- [x] **图谱漫游模式（Graph Tour）**：以某主题（如"液压系统安装"）为起点，AI 自动规划一条穿越相关节点的导览路径，逐步展开讲解每个节点的知识要点

---

### 七、图谱驱动的 AI 能力

**问答与推理**
- [ ] **图谱原生问答（KGQA）**：将用户自然语言问题翻译为 Cypher 查询（Text2Cypher），直接从图谱结构中精确提取答案（如"GJB 241 中涉及的所有力矩约束值"），补充向量检索的精确性不足
- [ ] **反向追问（Backward Chaining）**：给定一个结论（如某零件裂纹），沿因果关系链反向推导可能的根因工艺问题（Material 不合规 / Constraint 未满足 / Tool 磨损）
- [ ] **工艺路线规划**：给定零件和目标状态，图谱自动推导最优工艺路线（拓扑排序 + 约束满足），输出有序的工序步骤清单
- [ ] **知识图谱问题生成**：基于图谱结构自动生成考核题目（如"根据 CPS1220 §3.2，安装液压接头时应使用哪种扭矩工具？"），用于工艺培训考核
- [ ] **异常工艺诊断**：描述一个工艺异常现象，图谱检索相关 Hazard / Constraint / Inspection 节点，LLM 结合图结构推断违规的工艺步骤和改正建议

**自动化与持续学习**
- [ ] **图谱自动补全**：检测孤立 Section 节点（无 Tool/Material/Process 关联），批量提交 LLM 重新提取实体，实现图谱的自愈式数据填充
- [ ] **关系预测（Link Prediction）**：训练 TransE / RotatE 等知识图谱嵌入模型，预测可能缺失的关系（如某 Section 可能还 `REQUIRES_TOOL` 某 Tool，但提取时遗漏），置信度高于阈值时推荐给管理员确认
- [ ] **实体对齐（Entity Alignment）**：当导入来自不同供应商的规范时，自动识别不同文档中指称相同实体的节点（如"HB/T 5292" 与 "HB5292" 指同一标准），消除同义异名冗余
- [ ] **图谱嵌入持久化**：定期（每周）将所有节点的图结构 Embedding（Node2Vec / GraphSAGE）写入 Milvus，支持"结构相似节点检索"（超越纯文本相似度）
- [ ] **主动学习标注**：系统识别图谱中置信度低的边（如 `SIMILAR_TO` 分数在 0.8-0.9 之间的模糊关系），主动推送给领域专家确认或拒绝，持续提升图谱质量

---

### 八、协作与知识管理

- [ ] **专家知识录入界面**：领域专家通过结构化表单（非自由文本）直接向图谱录入工艺知识条目（Tool / Process / Constraint），系统自动生成对应节点和关系，降低知识入库门槛
- [ ] **图谱评审工作流**：新提取的节点/关系默认为 `draft` 状态，须经过至少一名领域专家审核（`APPROVED_BY`）后才进入正式检索，建立知识质量闸门
- [ ] **知识订阅与推送**：用户可订阅特定 Document 或 Component 的图谱变更（如文档更新版本），订阅事件触发站内消息或邮件通知
- [ ] **知识贡献排行**：统计每位用户审核通过的节点数、修正的实体合并数，形成知识贡献积分，激励专家参与图谱维护
- [ ] **问题挂载到图谱**：用户提问后，将问题节点（`Query`）与回答涉及的 Section 节点挂载，`(Query)-[:ANSWERED_BY]->(Section)`，形成"常见问题图谱"，高频问题对应的章节自动提升权重

---

### 九、运营与监控

**图谱健康度**
- [ ] **图谱健康度仪表盘**：专属管理页面实时展示六项核心指标：孤立节点数（无任何关系的节点）、悬空引用数（`REFERENCES` 目标不在库中的比例）、Constraint 覆盖率（有约束节点的 Section 占比）、实体提取待处理队列长度、近 7 天新增节点/关系趋势折线图；综合健康分低于阈值时页面顶部 Banner 警示，`GET /api/admin/graph/health`
- [ ] **悬空引用扫描**：`POST /api/admin/graph/scan-dangling` 扫描全库 `REFERENCES` 关系，列出目标文档不在库中的清单，结果写入 `SystemSetting`，每日定时自动触发；管理界面展示"待补充入库文档 Top 10"，一键跳转至批量导入页
- [ ] **实体覆盖率报告**：对每份文档统计有 Tool / Material / Process 关联的 Section 占比，覆盖率低于 30% 的文档标记为"实体提取不完整"，`GET /api/admin/documents/coverage-report` 返回文档级覆盖度排行，支持批量触发 `/reanalyze` 补跑
- [ ] **图谱一致性校验**：定期脚本检查：① Section 有 `doc_id` 但找不到父 Document；② Constraint 有 `chunk_id` 但关联 Section 已删除；③ `NEXT_SECTION` 关系是否形成环路；④ 图片节点 `path` 指向的文件是否仍然存在；发现异常写入 `audit_logs`，并在健康度仪表盘高亮显示

**变更管理**
- [ ] **图谱变更日志**：记录每次节点创建/修改/删除、关系新增/删除的操作日志（`operator`, `timestamp`, `operation_type`, `entity_type`, `entity_id`, `before`, `after`），存入 PostgreSQL `graph_changelog` 表；`GET /api/admin/graph/changelog?since=&type=&operator=` 支持多维过滤，`GET /api/admin/graph/changelog/{id}` 查看变更前后快照对比
- [ ] **变更回滚**：`POST /api/admin/graph/changelog/{id}/rollback` 执行单条变更的反向操作（删除→重建、属性修改→还原旧值、关系删除→重建），支持按时间段批量回滚同一操作集，回滚前要求管理员二次确认
- [ ] **增量同步 API**：`GET /api/graph/changelog?since=2026-01-01&format=ndjson` 返回指定时间后的图谱变更列表（JSON Patch 格式，含节点属性 diff），支持 ETag 增量拉取；供下游系统（ERP / MES / PLM）定时订阅，实现工艺知识库与制造执行系统的双向同步
- [ ] **图谱备份与时间点恢复**：APScheduler 定时任务（每日凌晨 2:00）触发 `neo4j-admin dump` 快照，压缩归档至对象存储（MinIO / S3），保留最近 30 天；`POST /api/admin/graph/restore?snapshot_id=` 支持回滚至任意历史快照，恢复前自动创建当前状态备份，满足等保三级审计留痕要求

**查询运营分析**
- [x] **查询热力分析**：统计哪些 Section 节点作为检索来源被引用最频繁，`GET /api/admin/analytics/hot-nodes?top_k=20&days=30` 输出热点节点排行
- [x] **检索策略效果对比**：按策略分组统计平均端到端延迟、好评率、平均来源数量、LLM token 消耗，`GET /api/admin/analytics/strategy-stats?days=30`
- [ ] **零结果查询监控**：记录 `sources` 为空的查询词，`GET /api/admin/analytics/empty-queries?days=7` 输出高频零结果词表，每周自动邮件推送至文档管理员，指导下一批 PDF 优先入库范围
- [x] **用户活跃度报表**：按用户 / 部门统计 DAU、周查询量、平均会话轮数，`GET /api/admin/analytics/user-activity?days=30`

**成本与资源监控**
- [x] **LLM 成本追踪**：每次 LLM 调用将 token 数和费用估算写入 `llm_usage` 表，`GET /api/admin/llm-costs?days=30&group_by=user|department|model|day` 多维度费用分摊报表
- [ ] **Token 预算告警**：`SystemSetting` 中存储各部门月度预算，消耗超过 80% 时推送预警，超过 100% 时自动降级至低价备用模型
- [ ] **存储容量监控**：定期统计 Neo4j 节点/关系总量、Milvus 向量条数与磁盘占用、PostgreSQL 各表大小，`GET /api/admin/storage/stats`
- [ ] **Prometheus + Grafana 运营大盘**：集成 `starlette-prometheus` 暴露 `/metrics` 端点，Grafana 大盘分"实时监控"与"运营周报"两个视角

**告警与通知**
- [ ] **多通道告警路由**：支持钉钉群机器人、企业微信 Webhook、邮件三种告警通道，按告警级别路由
- [ ] **告警聚合与静默**：同类告警 10 分钟内合并为一条推送，避免告警风暴；`POST /api/admin/alerts/silence` 支持维护窗口期间临时屏蔽
- [ ] **SLA 可用性统计**：以分钟为粒度记录 `/api/query` 和 `/api/query/stream` 的成功率，滚动计算 30 天 SLA，`GET /api/admin/sla`

---

### 十、垂直领域深化（航空制造专项）

- [ ] **适航符合性映射**：将工艺规范与适航条款（CCAR-25、FAR-25、CS-25）建立对应关系，支持适航审查时快速定位相关工艺依据
- [ ] **工艺 FMEA 图谱化**：将失效模式与影响分析（FMEA）结构化录入：`(Process)-[:HAS_FAILURE_MODE]->(FailureMode {severity, occurrence, detection, RPN})`，支持按 RPN 值排序高风险工序
- [ ] **特种工艺追踪**：为焊接、热处理、表面处理、无损检测等特种工艺建立专属节点类型，关联认证要求（操作者资质、设备鉴定周期）
- [ ] **首件鉴定关联**：将首件鉴定报告（FAI）与相关工艺章节挂钩，`(Document {type:"FAI"})-[:VALIDATES]->(Section)`，支持"这个工序的首件鉴定状态"查询
- [ ] **工程更改单（ECO）图谱**：将 ECO 作为图谱中的一等公民节点，连接变更前/后的 Section 节点和受影响的 Component 节点，实现工程变更的全链路追踪
