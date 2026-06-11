# KG-RAG 项目总览

> CPS 知识库 — 航空工艺规范 GraphRAG 智能问答系统
> 最后更新：2026-06-11

---

## 项目演进路径

```
A(规范生成) → B(用户体验) → C(系统运维) → D(高级查询)
→ E(智能评测) → F(数据治理) → G(多租户) → H(业务集成)
→ I(私有化部署) → J(数据可视化) → K(工艺仿真)
```

---

## 11 个核心模块

| # | 模块 | 核心能力 | 关键文件数 |
|---|------|----------|-----------|
| A | 规范生成引擎 | 五类工艺规范自动生成 + YAML 提示词 | ~15 |
| B | 用户体验优化 | 键盘快捷键/草稿/PWA/会话管理 | ~20 |
| C | 系统运维工程 | CI/CD/备份/日志/告警/负载测试 | ~25 |
| D | 高级查询能力 | 约束查询/版本溯源/跨文档引用 | ~15 |
| E | 智能评测体系 | MCQ评测/数据集管理/评测运行报告 | ~20 |
| F | 数据治理体系 | RBAC/审计/生命周期/版本控制/质量监控 | ~30 |
| G | 多租户支持 | 行级隔离/配额/计费/平台超管 | ~20 |
| H | 业务系统集成 | PLM/MES/ERP/SSO/Webhook/开放API | ~25 |
| I | 离线和私有化部署 | 部署检测/本地LLM/加密/等保/HA/微调 | 29 |
| J | 数据可视化深度 | 图表库/洞察仪表盘/报表/NL-SQL/实时流 | 46 |
| K | 工艺仿真集成 | 仿真导入/规范关联/参数查询/DOE/规则提取 | 21 |

---

## 代码规模统计

| 维度 | 数量 |
|------|------|
| **Python 文件** | 432 |
| **Python 代码行** | 53,686 |
| **TypeScript/TSX 文件** | 356 |
| **前端代码行** | 45,531 |
| **总文件数** | 788 |
| **总代码行** | ~99,000 |
| **数据库表** | 54 |
| **API 路由文件** | 124 |
| **API 端点** | 445+ |
| **前端页面** | 83 |
| **服务模块目录** | 30 |
| **Shell 脚本** | 18 |
| **Git 提交数** | 393+ |

---

## 技术栈

### 后端
- **框架**：FastAPI (async) + SQLAlchemy (async) + Alembic
- **数据库**：PostgreSQL 16（主库）+ Redis 7（缓存/队列）
- **图数据库**：Neo4j 5（知识图谱 + 仿真关联）
- **向量库**：Milvus / pgvector
- **对象存储**：MinIO（文件/仿真结果/报告）
- **任务队列**：Celery + Redis
- **认证**：JWT + OIDC/LDAP (SSO) + API Key

### AI/ML
- **LLM 推理**：Ollama / vLLM / TGI（本地）+ OpenAI 兼容 API
- **Embedding**：BGE-M3（本地）
- **Reranker**：BGE-Reranker-v2-M3
- **多模态**：Qwen2-VL / InternVL2
- **微调**：LLaMA-Factory / axolotl (LoRA)
- **GNN**：PyTorch Geometric

### 前端
- **框架**：Next.js 14 (App Router) + TypeScript
- **样式**：Tailwind CSS（暗色主题）
- **图表**：Recharts + D3.js
- **状态**：React Hooks（无外部状态库）
- **实时**：WebSocket + SSE

### 安全
- **加密**：AES-256-GCM（字段级）+ TLS 1.3（传输层）
- **密钥**：File / HashiCorp Vault / Env 三后端
- **合规**：等保 2.0 三级（5 控制域）
- **扫描**：Trivy（镜像）+ Bandit（Python）+ gitleaks（密钥）

### 基础设施
- **容器**：Docker Compose（单机）+ HA 多副本配置
- **集群**：Slurm/PBS（仿真 HPC）
- **代理**：Nginx（TLS 终止 + 负载均衡）
- **CI/CD**：GitHub Actions（测试/构建/安全扫描/发布）

---

## 核心能力清单（90+ 功能点）

### 智能问答
- [x] 六种检索策略（向量/全文/混合/实体/图谱/结构化）
- [x] RRF 融合重排序 + BGE-Reranker 精排
- [x] LLM 答案生成（流式输出）
- [x] 来源溯源 + 章节跳转
- [x] 会话管理（历史 + 收藏 + 分享）
- [x] 上下文感知多轮对话
- [x] 反事实推理（"如果X发生会怎样"）
- [x] 约束范围查询（参数在某范围内的规范）
- [x] 实体感知检索（材料/工艺/设备实体识别）
- [x] 跨文档引用追踪

### 知识图谱
- [x] 多模态 PDF 解析（文字/表格/公式/图像）
- [x] 7 类节点（Document/Section/Entity/Concept/Requirement/Process/SimulationCase）
- [x] 18 类关系（HAS_SECTION/REFERENCES/VALIDATED_BY 等）
- [x] 图谱可视化（力导向/层级树/时间线/矩阵视图）
- [x] GNN 链接预测（新增关联推荐）
- [x] 时间线演化视图
- [x] 知识空白分析（孤立节点/稀疏区域）

### 规范生成
- [x] 工艺规范自动生成（5 种模板类型）
- [x] YAML 提示词库管理
- [x] 生成历史与版本对比
- [x] 一键导出 PDF/Word

### 用户与权限
- [x] JWT 认证 + 工号登录
- [x] RBAC（角色权限矩阵）
- [x] SSO（OIDC / LDAP）
- [x] 多租户行级隔离
- [x] 操作审计日志（全链路）
- [x] 字段级数据脱敏
- [x] API Key 管理（作用域 + 速率限制）

### 数据治理
- [x] 文档生命周期管理（草稿/审核/发布/归档/销毁）
- [x] 文档版本控制（diff + 回滚）
- [x] 数据质量监控（完整性/一致性/时效性）
- [x] 等保 2.0 合规报告
- [x] GDPR 合规检查

### 系统集成
- [x] PLM/MES/ERP 标准适配器
- [x] Webhook 事件推送
- [x] 开放 API 平台（v1 RESTful）
- [x] 消息通知（钉钉/企业微信/邮件）
- [x] 数据导入/导出（Excel/CSV/JSON）

### 私有化部署
- [x] 四种部署模式（cloud/hybrid/intranet/airgapped）
- [x] 本地 LLM 管理（Ollama/vLLM/TGI）
- [x] 离线安装包（一键打包 + 安装 + 升级）
- [x] TLS 全链路加密 + 自签证书生成
- [x] AES-256-GCM 字段级加密
- [x] 多后端密钥管理 + 轮换审计
- [x] HA 部署（PG 主从 + Redis Sentinel + Nginx LB）
- [x] 灾备演练脚本（5 场景）
- [x] LoRA 微调（数据采集 + 训练 + 部署）

### 数据可视化
- [x] 12 个图表组件（Line/Bar/Pie/Area/Scatter/Radar/HeatMap/Gauge/TreeMap/Timeline）
- [x] DataSource 多数据源抽象（REST/WS/SSE/静态）
- [x] Chart DSL 声明式配置
- [x] 业务洞察仪表盘（4 领域 + 周期切换）
- [x] 拖拽式报表搭建器（10 种 widget）
- [x] NL→SQL 数据探索
- [x] 实时事件流（WebSocket + 暂停/继续）
- [x] PDF/CSV/JSON 报告导出
- [x] 5 种预置报表模板（月报/周报/季报/日报/安全）
- [x] 数据故事讲述

### 工艺仿真集成
- [x] 5 张仿真数据表（case/parameter/result/rule/workflow）
- [x] 多格式导入（Abaqus/Ansys/Fluent/Nastran/CSV/JSON）
- [x] 自动规范关联（3 策略 + Neo4j 建边）
- [x] QA 答案增强（注入相关仿真案例+规则）
- [x] 参数化检索（温度/压力范围 + 材料 + 载荷）
- [x] 参数空间散点可视化 + 空白区域建议
- [x] 案例对比（2-4 个并排 + 趋势分析）
- [x] DOE 采样（全因子/LHS/Sobol/自适应）
- [x] Slurm/PBS 集群提交 + 进度监控
- [x] 经验规则提取（设计规则/关键因子/失败模式）
- [x] 仿真中心仪表盘

---

## 商业化能力

| 能力 | 状态 | 说明 |
|------|------|------|
| 多租户 SaaS 化 | ✅ | 行级隔离 + 配额 + 计费 |
| 套餐订阅 | ✅ | basic/pro/enterprise 三档 |
| 开放 API 平台 | ✅ | RESTful v1 + API Key + 速率限制 |
| 业务系统集成 | ✅ | PLM/MES/ERP/SSO/Webhook |
| 私有化部署 | ✅ | 离线安装包 + 等保合规 |
| 数据安全认证 | ✅ | 等保 2.0 三级 + AES-256 + TLS 1.3 |

---

## 下一步建议

1. **Grafana 运营大盘**：接入 `starlette-prometheus`，建立 QPS/P99/LLM费用趋势实时大盘，是当前 `2%` 缺口中最高价值的一项。

2. **仿真求解器深度集成**：为 Abaqus/Ansys 二进制文件实现真实解析（需引入 `odbAccess` / `pyansys` 等商业 SDK），目前为 stub 降级实现。

3. **RAG 效果持续优化**：利用 K 模块沉淀的仿真案例数据集定期运行 E 模块评测，形成"仿真→评测→微调"的闭环。

4. **移动端 PWA 增强**：当前 PWA 离线缓存覆盖基础查询；可扩展至离线知识库浏览，适配车间现场使用场景。

5. **仿真结果大文件存储**：当前仿真结果图像/文件路径存 MinIO；可增加流式预览（支持 GB 级 .odb 文件分片加载）。

---

*由 Claude Sonnet 4.6 协助生成 · 2026-06-11*
