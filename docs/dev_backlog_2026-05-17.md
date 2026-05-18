# CPS 知识库 — 开发待办清单（2026-05-17）

> 来源：[功能审计报告](./feature_audit_2026-05-17.md)（2026-05-17）
> 范围：审计判定为 🔴 未实现 / 🟡 部分实现，需要补完或决策的功能。
> 不含：已 🟢 实现的功能、⚫ 外网依赖功能、README 路线图中的长期规划（K8s/CI/CD/API 版本管理等）。

## 摘要

| 优先级 | 条目数 | 总估时 | 变更说明 |
|--------|--------|--------|---------|
| P0     | 2      | 1.5 人天  | F038/F107 已关闭；F113+F114 已实现关闭（-2条 -1天） |
| P1     | 7      | 9.0 人天  | F055 验证升 🟢；F073 已实现关闭；F120 新增（+1条 +0.5天） |
| P2     | 5      | 10.5 人天 | F100 已实现关闭；F121 新增（+1条 +0.5天） |
| 合计   | 14     | 21.0 人天 | 较初版 -5条 -2.5天 |

> 估时按"单人开发，串行"计，不含 code review 时间。
> 最后更新：2026-05-18 遗留分析（F120+F121 新增；预存在改动分类完成）。

---

## P0 — 高优先级（生产安全 + 文档诚实）

---

### ~~F113 文件上传防护~~ CLOSED

**状态**：~~待开发~~ **✅ CLOSED 2026-05-17**
**优先级**：P0

**实现**：
- 新增 `src/services/security/upload_validator.py`：MIME 白名单（PDF-only）+ 文件大小 + magic number 三层校验
- `/api/preview` 接入完整 `validate_upload()`；`/api/ingest` 补 size 检查（已有内联 magic+type 校验）
- `MAX_UPLOAD_FILE_BYTES = 100 MB`（L2 业务层）

**验证**：伪装 PDF → 400；.exe → 400；空文件 → 400；120MB → 413（L1 拦截）

---

### ~~F114 请求体大小限制~~ CLOSED

**状态**：~~待开发~~ **✅ CLOSED 2026-05-17**
**优先级**：P0

**实现**：
- 新增 `src/middleware/body_size_limit.py`：`BodySizeLimitMiddleware` 通过 `Content-Length` 头快速拒绝，不消耗 stream
- 注册为最外层中间件（先于 CORS 执行）
- `MAX_REQUEST_BODY_BYTES = 50 MB`（L1 全局兜底）

**验证**：正常请求 → 200；60MB JSON body → 413

---

### F115 LLM API 重试与熔断

**状态**：待开发
**优先级**：P0
**审计来源**：[feature_audit_2026-05-17.md#f115-llm-api-重试与熔断](./feature_audit_2026-05-17.md#f115-llm-api-重试与熔断)

**任务描述**：
LLM 调用无重试机制，单次网络抖动或 Ollama 重启直接返回 500。需添加指数退避重试（≤ 3 次）和连续失败熔断（5 次失败 → 短路 60s）。注意：SSE 层已有的业务错误处理（`quota_exceeded` 等）不在此范围，熔断仅针对连接级错误。

**关键文件路径**：
- `backend/src/services/ai/llm_service.py` — `chat()` 方法加重试装饰器
- `backend/src/core/config.py` — `LLM_RETRY_MAX=3`, `LLM_CB_FAILURE_THRESHOLD=5`, `LLM_CB_TIMEOUT=60`

**实现思路**：
- 引入 `tenacity`：`@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))`
- 熔断计数写 Redis，连续失败 5 次后 60s 内直接抛 `CircuitOpenError` → 返回 503
- 熔断状态暴露至 `GET /api/health` 的响应体

**估时**：一天

**验收标准**：
- [ ] 停掉 Ollama，发查询 → 重试 3 次后返回 503（日志可见 3 次尝试）
- [ ] 连续触发熔断后，后续请求立即返回 503（不等重试超时）
- [ ] 重启 Ollama 后，60s 内自动恢复正常

**依赖**：无

---

### F116 优雅关闭（Graceful Shutdown）

**状态**：待开发
**优先级**：P0
**审计来源**：[feature_audit_2026-05-17.md#f116-优雅关闭graceful-shutdown](./feature_audit_2026-05-17.md#f116-优雅关闭graceful-shutdown)

**任务描述**：
SIGTERM 未处理，重启部署时正在进行的 SSE 流被立即切断，前端收到不完整响应。需在 FastAPI `lifespan` 的 shutdown 阶段等待活跃流结束后再退出（最多等 30s）。

**关键文件路径**：
- `backend/src/main.py` — `lifespan` 上下文管理器 shutdown 阶段
- `backend/src/routers/query/stream.py` — 活跃流计数器（进入 +1，退出 -1）
- `docker-compose.yml` — `stop_grace_period: 30s`

**实现思路**：
- 全局 `asyncio.Event` 作为 shutdown 信号；`active_streams` 原子计数器
- `lifespan` shutdown：发信号 → 最多等 30s 直到计数归零 → 退出
- SSE 流每次进入 / 退出时维护计数

**估时**：半天

**验收标准**：
- [ ] 正在流式回答时 `kill -SIGTERM <pid>`，响应完整输出后进程才退出
- [ ] 超过 30s 的流被强制关闭（进程不无限等待）
- [ ] `docker compose restart backend` 前端无 SSE 中断错误

**依赖**：无

---

### ~~F107 零结果查询监控~~ CLOSED

**状态**：🟢 已实现 — verified_at: 2026-05-17, method: alembic + curl smoke test
**优先级**：P0
**审计来源**：[feature_audit_2026-05-17.md#f107--零结果查询监控get-apiadminanalyticsempty-queries](./feature_audit_2026-05-17.md#f107--零结果查询监控get-apiadminanalyticsempty-queries)

**任务描述**：
端点 `GET /api/admin/analytics/empty-queries` 不存在，且数据未采集（`LLMUsage` 无 `sources_count` 字段）。必须分两阶段：阶段 1 补数据采集，阶段 2 再实现端点；跳过阶段 1 直接做阶段 2 将永远返回空数据。

**关键文件路径**：
- `backend/src/db/models.py` — `LLMUsage` 加 `sources_count: int` 字段
- `backend/alembic/versions/` — 对应 migration
- `backend/src/routers/query/stream.py` — 流结束时写入 `sources_count=len(sources)`
- `backend/src/routers/admin_api/analytics.py` — 新增 `GET /analytics/empty-queries` 端点

**实现思路**：
- 阶段 1：`stream.py` 流结束时记录 `sources_count`（0 = 零结果）到 `LLMUsage`
- 阶段 2：`analytics.py` 查 `sources_count == 0` 记录，按 `question` 分组聚合，输出频率排行

**估时**：一天

**验收标准**：
- [ ] 发一次无命中查询，`llm_usage` 表中 `sources_count=0` 有新记录
- [ ] `GET /api/admin/analytics/empty-queries?days=7` 返回合法 JSON
- [ ] 端点在无零结果数据时返回空数组（非 500）

**依赖**：无

---

### ~~F038 导入进度：路径决策（WebSocket vs HTTP 轮询）~~

> **DECIDED 2026-05-17：路径 B — 沿用现有 HTTP 轮询机制。**
> README 已在 Step 2 修正为 `[ ] WebSocket（计划中，当前为 HTTP 轮询）`，状态准确。
> 本条任务关闭，无需代码变更。

---

## P1 — 中优先级（稳定性 + 名实相符）

---

### F031-pc PC 端图片上传问答

**状态**：🟡 部分实现（移动端 API 已实现，PC 端 UI 缺失）
**优先级**：P1
**审计来源**：[feature_audit_2026-05-17.md#f031--图片提问](./feature_audit_2026-05-17.md#f031--图片提问)

**任务描述**：
移动端图片提问 API 已实现，PC 端 query 页面无图片上传控件（无粘贴 / 点击上传）。README 已更正为"移动端 API 已实现，PC 端 UI 计划中"，本任务补充 PC 端 UI。

**关键文件路径**：
- `frontend/src/app/query/` — 输入区添加上传控件和粘贴监听
- `frontend/src/app/query/useStreamQuery.ts` — 扩展 `sendMessage` 支持 `FormData`

**实现思路**：
- 输入区加 `<input type="file" accept="image/*">` 和 `paste` 事件监听
- 图片随消息持久化（参考移动端已有实现复用 API）
- 消息气泡中展示图片缩略图

**估时**：两天

**验收标准**：
- [ ] PC 浏览器下可点击上传图片，图片出现在输入区
- [ ] 粘贴截图后可发送，消息记录中可见图片
- [ ] 刷新页面后图片仍显示（已持久化）

**依赖**：无（移动端 API 可直接复用）

---

### ~~F055 主查询管线接入实体感知检索~~

> **CLOSED 2026-05-17：验证结果为 🟢 已实现。**
> `core.py:201` `apply_entity_aware()` 已在主管线无条件调用（Neo4j 可用时），
> `graph_expansion.py:32` 含完整 `REQUIRES_TOOL|USES_MATERIAL|INVOLVES_PROCESS` 实现。
> 审计报告已同步升级 F055 🟡→🟢。无需开发。

---

### F056 自动策略选择接入主管线

**状态**：🟡 部分实现（路由逻辑已有，未驱动实际策略）
**优先级**：P1
**审计来源**：[feature_audit_2026-05-17.md#f056--自动策略选择](./feature_audit_2026-05-17.md#f056--自动策略选择)

**任务描述**：
自动策略路由逻辑（关键词分类）已实现，但 `strategy="auto"` 分支未实际驱动策略选择，用户选"自动"时走固定策略。

**关键文件路径**：
- `backend/src/routers/query/stream.py` — `strategy == "auto"` 分支
- `backend/src/services/retrieval/auto_strategy.py`（或类似路径）

**实现思路**：
- `auto` 分支调用策略分类器，得到推荐策略名（`parallel` / `multi_hop` 等）
- 将推荐策略替换后走对应分支处理
- 响应中加 `strategy_used` 字段，供前端可选展示

**估时**：一天

**验收标准**：
- [ ] 发明显多跳问题，响应中 `strategy_used` 为 `multi_hop`
- [ ] 发简单查询，`strategy_used` 为 `parallel`
- [ ] `strategy="auto"` 不再固定走同一策略

**依赖**：无

---

### F117 PDF 入库 Celery 异步化

**状态**：待开发（Celery 框架已引入，未接主入库流程）
**优先级**：P1
**审计来源**：[feature_audit_2026-05-17.md#f117-异步任务队列](./feature_audit_2026-05-17.md#f117-异步任务队列)

**任务描述**：
PDF 入库同步阻塞（耗时 > 30s），HTTP worker 长期被占用。需将 `/api/ingest` 改为提交 Celery 任务后立即返回 `task_id`，实际处理异步执行，前端用现有轮询机制查询进度。

**关键文件路径**：
- `backend/src/routers/docs/upload.py` — 提交 Celery 任务，返回 202 + `task_id`
- `backend/src/tasks/ingest_task.py`（需新建）— 入库逻辑封装为 Celery task
- `backend/src/services/ingestion/processing_tracker.py` — 进度写入复用（已有）

**实现思路**：
- `upload.py`：保存临时文件 → `ingest_task.delay(filepath, task_id)` → 返回 202
- `ingest_task`：复用 `batch_ingest_service.py` 逻辑，写进度到 Redis
- 前端轮询逻辑不变，后端由同步改异步

**估时**：两天

**验收标准**：
- [ ] `POST /api/ingest` 立即返回 202 + `task_id`（< 1s）
- [ ] `GET /api/ingest/status/{task_id}` 轮询可见进度递增
- [ ] 任务失败时状态为 `failed`，前端可展示

**依赖**：无（Celery 已配置）

---

### ~~F073 PostgreSQL 索引补齐~~ CLOSED

**状态**：🟢 已实现 — verified_at: 2026-05-17, method: direct SQL + psql \di
**优先级**：P1
**审计来源**：[feature_audit_2026-05-17.md#f073-postgresql-索引补齐](./feature_audit_2026-05-17.md#f073-postgresql-索引补齐)

**任务描述**：
`conversations` 表缺少 `user_id` 索引，按用户查询历史为全表扫描，随用户量增长成为性能瓶颈。需补索引并验证查询计划改善。

**关键文件路径**：
- `backend/alembic/versions/` — 新增 migration（`CREATE INDEX idx_conversations_user_id`）
- `backend/src/db/models.py` — `Conversation` 模型声明 `Index`

**实现思路**：
- 补 `user_id`、`created_at` 索引（常用过滤 + 排序列）
- `EXPLAIN ANALYZE SELECT ... WHERE user_id=?` 验证改为 Index Scan
- migration 要有可用的 `downgrade()`

**估时**：半天

**验收标准**：
- [ ] Migration `upgrade` + `downgrade` 均无错执行
- [ ] `EXPLAIN ANALYZE` 显示 `Index Scan`（非 `Seq Scan`）
- [ ] 历史数据无损（行数前后一致）

**依赖**：无

---

### F118 Embedding 批处理

**状态**：待开发
**优先级**：P1
**审计来源**：[feature_audit_2026-05-17.md#f118-embedding-批处理](./feature_audit_2026-05-17.md#f118-embedding-批处理)

**任务描述**：
Embedding 服务逐条 encode，入库速度是主要瓶颈（bge-m3 CPU 模式尤甚）。改为批处理可充分利用矩阵运算，显著提升入库吞吐。

**关键文件路径**：
- `backend/src/services/ai/embedding_service.py` — `encode()` 改为 `encode_batch(texts: list[str])`

**实现思路**：
- 新增 `encode_batch(texts, batch_size=32)`，内部分批调用模型
- 入库服务在 chunk 列表上批量调用，减少模型调用次数
- `EMBEDDING_BATCH_SIZE` 写入 `settings`

**估时**：一天

**验收标准**：
- [ ] 入库 100 chunk 耗时相比逐条模式下降 ≥ 30%（本地计时对比）
- [ ] 批量结果与逐条结果 L2 距离 < 1e-5（精度不变）
- [ ] `EMBEDDING_BATCH_SIZE` 可通过 `.env` 调整

**依赖**：无

---

### F060 Reranker 内容截断改为按 token

**状态**：🟡 已验证待实现（`reranker.py:135` 确认 `[:1024]` 字符截断，verified 2026-05-17）
**优先级**：P1
**审计来源**：[feature_audit_2026-05-17.md#f060--reranker-精排](./feature_audit_2026-05-17.md#f060--reranker-精排)

**任务描述**：
验证确认：`reranker.py:135` 使用 `[:1024]` 字符切片，注释"1024 chars ≈ 512 tokens"为估算非精确计数。中英文混合时实际 token 数超出 bge-reranker 512 token 上限，影响精排质量，需改为 tokenizer 精确计数后截断。

**关键文件路径**：
- `backend/src/services/retrieval/reranker.py:135` — 将 `[:1024]` 改为按 tokenizer token 数截断

**实现思路**：
- 用 `transformers.AutoTokenizer` 加载 bge-reranker tokenizer，计算真实 token 数
- 截断时保持在 512 token 以内（tokenizer 实例复用，避免重复加载）

**估时**：半天

**验收标准**：
- [ ] 长中文 chunk（500 字）rerank 后不再出现 `Token indices sequence length` 警告日志
- [ ] token 超 512 的 chunk 截断后 rerank 正常返回（不报错）
- [ ] 短文本（< 100 字）不受影响

**依赖**：无

---

### F049 实体节点可视化渲染验证 / F076 通用配置热重载实现

**状态（F049）**：PENDING_VERIFICATION（需前端启动，2026-05-17 服务未运行）
**状态（F076）**：🔴 确认未实现（代码级验证：全库无 watchdog/FileSystemEvent，只有局部 reload 端点）
**优先级**：P1
**审计来源**：[feature_audit_2026-05-17.md#f049--实体节点渲染](./feature_audit_2026-05-17.md#f049--实体节点渲染) · [#f076--配置热重载](./feature_audit_2026-05-17.md#f076--配置热重载)

**任务描述**：
F049：需前端启动后目视检查 Tool / Material / Process 节点颜色 / 图标是否与 Section 有区分（PENDING_VERIFICATION）。F076：代码已确认不支持通用热重载，全库无 watchdog/FileSystemEvent，仅有 synonyms / entity / GNN 局部 reload；需实现通用机制。

**关键文件路径**：
- F049：`frontend/src/app/graph/` — 节点渲染配置（验证即可）
- F076：`backend/src/core/config.py` + `backend/src/startup.py` — 热重载机制新增

**实现思路（F076）**：
- 调研当前哪些配置已支持局部 reload（synonyms / entity / GNN）
- 在 `startup.py` 新增 watchdog 线程监听 `.env` 变化，或新增 `POST /api/admin/config/reload` 触发端点
- settings 重新加载后广播至各 service（LLM provider / retrieval config 等）
- 验收：改 `.env` 中某配置项后，5 秒内 `GET /api/admin/config` 返回新值

**估时**：F049 半天（验证）；F076 一天（半天调研 + 半天实现）

**验收标准**：
- [ ] F049：图谱页 Tool / Material 节点与 Section 节点颜色 / 形状不同（PENDING_VERIFICATION）
- [ ] F076：修改 `.env` 某配置项后 5 秒内无需重启即可读到新值

**依赖**：F049 需前端启动；F076 无依赖

---

### F120 PDF 解析异常优雅降级

**状态**：待开发
**优先级**：P1
**审计来源**：F113 验证测试 #1 发现（2026-05-17）

**任务描述**：
通过 F113 上传校验（magic bytes 匹配）的 PDF，若 pdfplumber/pdfminer 解析失败（损坏、加密、0 字节内容等），当前直接返回 500 并暴露内部异常。应在 `/api/preview` 的 `parse()` 调用处捕获解析异常，返回 422 + 友好消息。

**关键文件路径**：
- `backend/src/routers/docs/ingest.py:170` — `preview()` 函数，`parse(tmp_path)` 调用无 try/except

**实现思路**：
在 `parse()` 调用外包 try/except，捕获 `Exception`，返回 `HTTPException(422, "PDF 解析失败：{原因}")`，`backend.log` 记录详细 traceback（不暴露给客户端）。

**估时**：半天

**验收标准**：
- [ ] 上传 28 字节假 PDF 返回 422 而非 500
- [ ] 上传加密 PDF 返回 422 + "需要密码"
- [ ] 上传损坏 PDF 返回 422 + "无法解析"
- [ ] backend.log 记录解析失败原因，traceback 不出现在 HTTP 响应体

**依赖**：F113（已闭环）

---

## P2 — 低优先级（功能增量 / 体验优化）

---

### F121 上传校验统一为多文件类型

**状态**：待开发
**优先级**：P2
**审计来源**：F113 实现过程发现（2026-05-17）

**任务描述**：
当前 `validate_upload()` 是 PDF-only，`/api/ingest` 保留了独立的内联多类型校验（PDF/DOCX/DOC）。DOCX/DOC pipeline 完整（LibreOffice 转换 → pdfplumber 解析），支持是真实需求。两套逻辑并存，长期维护成本高。需扩展 `validate_upload()` 支持多类型白名单，统一两处逻辑。

**关键文件路径**：
- `backend/src/services/security/upload_validator.py` — 扩展支持多 MIME 类型 + 对应 magic bytes
- `backend/src/routers/docs/ingest.py` — 移除内联校验，改用 `validate_upload()`

**实现思路**：
- `validate_upload(allowed_types={"application/pdf"})` 变为可配置白名单
- DOCX magic: `PK\x03\x04`，DOC magic: `\xd0\xcf\x11\xe0`
- 调用方传入允许的类型集合，不全局开放（避免成为漏洞）

**估时**：半天

**验收标准**：
- [ ] `/api/ingest` 接受 PDF、DOCX、DOC，拒绝 .exe
- [ ] `/api/preview` 仍然只接受 PDF
- [ ] 内联校验代码从 ingest.py 删除

**依赖**：F113（已闭环）

---

### F110 图谱快照 URL 分享

**状态**：🔴 未实现
**优先级**：P2
**审计来源**：[feature_audit_2026-05-17.md#f110--图谱快照与分享url-可分享快照](./feature_audit_2026-05-17.md#f110--图谱快照与分享url-可分享快照)

**任务描述**：将图谱视图状态（过滤条件、高亮节点、缩放位置）序列化为 URL query string，分享链接可复现完全相同视图。

**关键文件路径**：
- `frontend/src/app/graph/` — 视图状态序列化 + URL sync 逻辑

**估时**：两天

**验收标准**：
- [ ] 复制当前图谱 URL，新标签页打开，过滤条件和高亮状态完全一致

**依赖**：无

---

### F079 对话分支

**状态**：🔴 未实现
**优先级**：P2
**审计来源**：[feature_audit_2026-05-17.md#f079--对话分支](./feature_audit_2026-05-17.md#f079--对话分支)

**任务描述**：支持从某条 AI 消息处新开分支，探索不同追问路径。涉及数据模型（`Message` 加 `parent_message_id`）和前端树状分支 UI，工作量较大。

**关键文件路径**：
- `backend/src/db/models.py` — `Message` 表加 `parent_message_id` + migration
- `frontend/src/app/query/` — 消息分支选择 UI

**估时**：一周

**验收标准**：
- [ ] 点击某条 AI 消息的"分支"按钮，可在新分支继续提问
- [ ] 切换分支时消息列表正确切换，不混淆

**依赖**：无

---

### F022 移动端响应式补齐

**状态**：🟡 部分实现（基础布局已适配，图谱页 / 对比页有问题）
**优先级**：P2
**审计来源**：[feature_audit_2026-05-17.md#f022--移动端适配](./feature_audit_2026-05-17.md#f022--移动端适配)

**任务描述**：移动端基础布局已适配，图谱页和文档对比页在小屏幕下有溢出或操作不可用问题，需逐页检查修复。

**关键文件路径**：
- `frontend/src/app/graph/` — 图谱页移动端布局
- `frontend/src/app/docs/compare/` — 对比页移动端布局

**估时**：一天

**验收标准**：
- [ ] 375px 宽度下图谱页无横向溢出，工具栏可访问
- [ ] 375px 宽度下文档对比页两栏内容可滚动浏览

**依赖**：无

---

### F039 前端 Vitest 测试补全

**状态**：🟡 部分实现（框架已配置，覆盖率不足）
**优先级**：P2
**审计来源**：[feature_audit_2026-05-17.md#f039--前端单元测试vitest](./feature_audit_2026-05-17.md#f039--前端单元测试vitest)

**任务描述**：Vitest 框架已配置但测试覆盖率不足，需针对核心 Hook（`useStreamQuery`、`useConversation`）和工具函数补充单元测试。

**关键文件路径**：
- `frontend/src/app/query/useStreamQuery.test.ts`（需新建）
- `frontend/src/lib/*.test.ts`（覆盖工具函数）

**估时**：两天

**验收标准**：
- [ ] `pnpm test` 通过，核心 Hook 覆盖率 ≥ 60%
- [ ] SSE 断线重连逻辑有测试覆盖

**依赖**：无

---

### ~~F100 快捷键帮助面板（? 键浮层）~~ CLOSED

**状态**：🟢 已实现 — verified_at: 2026-05-17, method: Playwright browser test
**优先级**：P2

> 新建 `ShortcutsModal.tsx`（77 行），`useKeyboard.ts` 注册 `?` 监听，挂载于 ConditionalLayout 两个分支。Playwright (a)-(e) 全 PASS。
