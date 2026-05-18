# P1/P2 剩余任务执行清单（2026-05-17）

## 摘要
- 总任务数：15
- 已完成：4（F049、F060、F120、F121）
- 待完成：11
- 估算工时：28.0 人天
- LLM 依赖任务（GATED ON B001）：2 条
- 当前 HEAD：f77418d

## 工作纪律（每条任务执行前必读）

P1. 每个任务做完，必须：
    - git status --short 为空（工作区 clean）
    - 任务对应的 audit + backlog 更新到位
    - 至少有一个 commit 落地
    - 才能开始下一个任务

P2. 每个任务的 commit 必须分层：
    - 实现 commit（代码改动）
    - 文档 commit（audit + backlog 更新）
    分别独立 commit，便于回滚

P3. 每次 commit 前 ：
    - git status --short 检查
    - 特别关注 ?? 行（未跟踪文件）
    - 任何未跟踪的 .py/.yaml/.ts/.tsx 必须解释来源：
      * 应入库 → git add
      * 应忽略 → 加到 .gitignore
      * 应丢弃 → 单独 stash 不要 git clean

P4. 不允许"自作主张顺手优化"：
    - 不要重写其他不相关的代码
    - 不要给"看起来不优雅"的代码做美化
    - 不要引入新的库依赖（pyproject.toml / package.json 不动）
    - 任何改动都必须对应某个明确任务

P5. 每个任务的验证必须可观察：
    - curl 状态码 / SQL 查询结果 / 浏览器行为描述
    - 不允许"代码逻辑分析"代替"实机验证"
    - 验证失败立刻停下来

中断条件（出现立刻停下来，等我回来）

任何以下情况立刻停止：

I1. 任务出现"代码逻辑正确但实际行为不符"
    （如 F049 那种最终 PASS 之外的情况）

I2. 工作区出现你不认识的未跟踪文件

I3. 一个任务做了 > 2 个工作小时还没闭环

I4. 任务发现"架构层选择"（A/B 两种实现路径）

I5. 任务发现"数据可能损坏"（如 schema 改动影响现有数据）

I6. git status 出现你不打算 commit 的 M 文件

I7. 测试中发现可能影响其他已闭环功能的副作用

I8. 任务 X 完成后发现任务 Y 需要重做（依赖错算）

I9. 任何 LLM 相关错误（说明 B001 还在）

I10. 任何 docker / 数据库 / 网络层无法解决的错误

## 已完成任务

### F049 实体节点可视化（已闭环 ✓）
- commit: 342dd5d
- 验证：Tool/Material/Process/Constraint 独立颜色 + GraphFilterPanel 过滤 + 详情侧栏均工作

### F060 reranker token 截断（已闭环 ✓）
- commits: 8495c1f, 948efd4
- 验证：tokenizer max_length 8192，单测 8/8 PASS

### F120 PDF 解析异常优雅降级（已闭环 ✓）
- commit: 3ef822e
- 验证：`/api/preview` 对坏 PDF 返回 422 + 友好消息；真实 PDF 仍正常

### F121 多类型上传校验统一（已闭环 ✓）
- commit: f77418d
- 验证：`/api/preview` 6 项 + `/api/ingest` 6 项，共 12 项回归全过；`validate_upload()` 支持 `allowed_types` 白名单

## 完成记录表

| 任务 | 结果 | commit | 验证摘要 |
|---|---|---|---|
| F049 | CLOSED | 342dd5d | Tool/Material/Process/Constraint 独立颜色 + 过滤 + 详情侧栏 |
| F060 | CLOSED | 8495c1f, 948efd4 | tokenizer max_length 8192，单测 8/8 PASS |
| F120 | CLOSED | 3ef822e | 坏 PDF 返回 422，真实 PDF 仍正常 |
| F121 | CLOSED | f77418d | 12 项回归全过，preview 保持 PDF-only，ingest 接入 DOCUMENT_TYPES |

## 待执行任务（按推荐顺序）

### 任务 1：F120 PDF 解析异常优雅降级
**优先级**：P1
**估时**：0.5 天
**类型**：实施型
**依赖 LLM**：否
**审计来源**：docs/feature_audit_2026-05-17.md#f120

**状态**：~~进行中~~ ✅ 已闭环

#### 背景
F113 上传校验放行格式合法的 PDF，但下游 pdfminer 解析失败时返回 500 + 暴露 traceback。是安全风险（DoS 攻击面）+ 用户体验问题。

#### 步骤
1. 查看 `backend/src/routers/docs/ingest.py` 第 170 行附近的 `preview()` 端点。
2. 将 `parse(tmp_path)` 调用包进 `try/except`。
3. 记录 `filename`、异常类型和 message 到 `backend.log`，不要把 traceback 暴露给客户端。
4. 用 3 个测试文件验证：
   - 28 字节假 PDF
   - 加密 PDF（如果有）
   - 真实但格式异常的 PDF
5. 逐个 `curl` 上传并确认返回 422。
6. 完成后分两个 commit：代码实现 + 文档归档。

#### 验收
- [x] 28 字节假 PDF 返回 422 + 友好消息（不是 500）
- [x] backend.log 记录 warning，不暴露完整 traceback
- [x] 加密 PDF 返回 422（如果有测试样本）
- [x] 真实 PDF 上传仍正常

#### 完成记录
- commit: `3ef822e`
- 验证：`pytest backend/tests/test_preview_endpoint.py` + `curl /api/preview`
- 备注：坏 PDF 返回 422 `无法解析 PDF：PdfminerException`，真实 PDF 仍返回 200

#### Commits
- Commit A: feat(F120): graceful PDF parse error
- Commit B: docs: mark F120 closed and update execution plan

---

### 任务 2：F121 多类型上传校验统一（已闭环 ✓）
**优先级**：P2
**估时**：0.5 天
**类型**：实施型
**依赖 LLM**：否
**审计来源**：docs/feature_audit_2026-05-17.md#f121

**状态**：~~进行中~~ ✅ 已闭环

#### 背景
当前 `validate_upload()` 是 PDF-only，`/api/ingest` 保留了独立的内联多类型校验（PDF/DOCX/DOC）。DOCX/DOC pipeline 完整（LibreOffice 转换 → pdfplumber 解析），支持是真实需求。两套逻辑并存，长期维护成本高。需扩展 `validate_upload()` 支持多类型白名单，统一两处逻辑。

#### 步骤
1. 查看 `backend/src/services/security/upload_validator.py`。
2. 将校验扩展为多类型支持：
   - PDF: `application/pdf`
   - DOCX: `application/vnd.openxmlformats-officedocument.wordprocessingml.document`
   - DOC: `application/msword`
3. 为不同 MIME 类型分别校验 magic bytes。
4. 修改 `/api/ingest` 为统一调用 `validate_upload()`。
5. 删除 `ingest.py` 的内联多类型校验逻辑。
6. 准备 6 个测试文件并逐个 `curl /api/ingest` 验证。

#### 验收
- [x] `/api/ingest` 接受 PDF、DOCX、DOC，拒绝 .exe
- [x] `/api/preview` 仍然只接受 PDF
- [x] 内联校验代码从 ingest.py 删除

#### 完成记录
- commit: `f77418d`
- 验证：F113 回归 6 项 + F121 新增 6 项，共 12 项全过
- 样本来源：`ok.pdf` / `ok.docx` / `ok.doc` 由本地生成；`evil.exe` / `empty.pdf` / `real.pdf 改后缀 .docx` 为本地构造

#### Commits
- Commit A: feat(F121): unify upload validation for PDF/DOCX/DOC
- Commit B: docs: mark F121 closed

---

### 任务 3：F076 配置热重载
**优先级**：P1
**估时**：1 天
**类型**：实施型 + 需架构选择
**依赖 LLM**：否

⚠️ 注意：此任务有 A/B/C 三种实现选项，按工作纪律 I4，必须停下来等用户决定再推进。

#### 背景
当前代码只存在零散的局部 reload，不存在通用配置热重载。目标是让部分运行时配置在不重启服务的情况下可刷新。

#### 步骤
1. 调研当前局部 reload 机制：
   - `grep -rn "reload\\|hot_reload\\|watch" backend/src/`
2. 搞清楚当前哪些配置可以局部重载。
3. 设计三种方案之一：
   - 选项 A：watchdog 监听 `.env` 文件变化，自动重载 Settings 对象
   - 选项 B：暴露 `POST /api/admin/config/reload` 端点，管理员手动触发重载
   - 选项 C：A + B 都做
4. 如果不确定选哪个，按工作纪律 I4 停下来等用户决定。
5. 如果选 B，新增 `backend/src/routers/admin_api/config_reload.py`。
6. 只热重载允许项：
   - TOP_K
   - 各种阈值
   - 各种 max_xxx
   - 日志级别
7. 不热重载这些需要重启才生效的配置：
   - DB 连接字符串
   - 端口
   - JWT secret
   - LLM provider 类型
8. 验证 `.env` 改动后无需重启即可读到新值。

#### 验收
- [ ] 修改 `.env` 某配置项后 5 秒内无需重启即可读到新值

#### Commits
- Commit A: feat(F076): config hot reload via admin API
- Commit B: docs: mark F076 closed

---

### 任务 4：F056 自动策略接通验证
**优先级**：P1
**估时**：0.5 天
**类型**：轻验证型
**依赖 LLM**：是 ⚠️ GATED ON B001
**审计来源**：docs/feature_audit_2026-05-17.md#f056--自动策略选择

#### 背景
自动策略路由逻辑（关键词分类）已实现，但 `strategy="auto"` 分支未实际驱动策略选择，用户选"自动"时走固定策略。

#### 步骤
1. `curl` 测试 `strategy="auto"` 的响应。
2. 看返回 JSON 是否带 `strategy_used` 字段。
3. 判断策略是否真根据题目类型变化。
4. 如果 B001 仍未解除，只做代码/单测层面检查，端到端验证跳过。

#### 验收
- [ ] 发明显多跳问题，响应中 `strategy_used` 为 `multi_hop`
- [ ] 发简单查询，`strategy_used` 为 `parallel`
- [ ] `strategy="auto"` 不再固定走同一策略

#### Commits
- Commit A: feat(F056): wire auto strategy selection into query pipeline
- Commit B: docs: mark F056 closed

---

### 任务 5：F031-pc PC 端图片上传问答
**优先级**：P1
**估时**：2 天
**类型**：实施型
**依赖 LLM**：否
**审计来源**：[feature_audit_2026-05-17.md#f031--图片提问](./feature_audit_2026-05-17.md#f031--图片提问)

#### 背景
移动端图片提问 API 已实现，PC 端 query 页面无图片上传控件（无粘贴 / 点击上传）。README 已更正为"移动端 API 已实现，PC 端 UI 计划中"，本任务补充 PC 端 UI。

#### 实现思路
- 前端：在 `ConversationInput` / query 输入区加图片上传区，支持 clipboard paste / drag-drop / file picker
- 后端：扩展 query endpoint 接受 `multipart/form-data` 或单独 `/api/query/with-image` 端点
- 关联：上传后图片随 message 持久化（Conversation 表）

#### 步骤
1. 调研当前 `ConversationInput` 组件结构。
2. 调研当前 query endpoint 是否支持图片。
3. 视调研结果决定：扩展现有 endpoint vs 新建专用 endpoint。
4. 实现前端 UI（参考 ChatGPT / Claude 的图片上传交互）。
5. 实现后端接受 + 路由到 VLM。
6. 测试：clipboard paste、drag-drop、file picker 三种方式。
7. 测试：上传后图片能在历史会话中重新看到。

#### 验收
- [ ] PC 端 query 页面可粘贴图片
- [ ] PC 端 query 页面可拖拽图片
- [ ] PC 端 query 页面可点击上传图片
- [ ] 上传的图片随消息持久化
- [ ] 历史会话能重新加载图片

#### Commits
- Commit A: feat(F031-pc-fe): image upload UI in query page
- Commit B: feat(F031-pc-be): accept image in query endpoint
- Commit C: docs: mark F031-pc closed

⚠️ 此任务是新功能开发不是 bug 修复，按工作纪律 I4（架构层选择），"扩展 endpoint vs 新建 endpoint" 这个决策必须停下来等用户。

---

### 任务 6：F022 移动端响应式补齐
**优先级**：P2
**估时**：1 天
**类型**：实施型 UI
**依赖 LLM**：否
**审计来源**：[feature_audit_2026-05-17.md#f022--移动端适配](./feature_audit_2026-05-17.md#f022--移动端适配)

#### 背景
移动端基础布局已适配，图谱页和文档对比页在小屏幕下有溢出或操作不可用问题，需逐页检查修复。

#### 步骤
1. 用 Chrome DevTools 切换到移动视口（375x667），逐页检查：login / query / library / graph / settings。
2. 列出布局问题清单（不要现场修）。
3. 优先级：query 页 > library 详情页 > 其他。
4. 修改 Tailwind 类（sm: md: lg: 前缀）。
5. 不要重写组件结构，只调 className。
6. 验证：375 / 414 / 768 三个视口。

#### 验收
- [ ] login 页移动视口可用
- [ ] query 页移动视口可用（输入框、消息、来源卡）
- [ ] library 页移动视口可用
- [ ] 桌面视口（>= 1024px）行为不变

#### Commits
- Commit A: feat(F022): responsive layout for mobile viewports
- Commit B: docs: mark F022 closed

---

### 任务 7：F079 对话分支
**优先级**：P2
**估时**：1-2 天
**类型**：实施型新功能
**依赖 LLM**：否
**审计来源**：[feature_audit_2026-05-17.md#f079--对话分支](./feature_audit_2026-05-17.md#f079--对话分支)

#### 背景
支持从某条 AI 消息处新开分支，探索不同追问路径。涉及数据模型（`Message` 加 `parent_message_id`）和前端树状分支 UI，工作量较大。

#### 关键文件路径
- `backend/src/db/models.py` — `Message` 表加 `parent_message_id` + migration
- `frontend/src/app/query/` — 消息分支选择 UI

#### 步骤（待用户确认数据模型 / UI 方案后细化）
1. 先明确分支的持久化模型与前端交互。
2. 评估 `Message` 表的关系改动是否需要迁移和回填。
3. 设计分支切换 UI 与消息列表切换逻辑。
4. 完成后再拆分实现 commit / 文档 commit。

#### 验收
- [ ] 点击某条 AI 消息的"分支"按钮，可在新分支继续提问
- [ ] 切换分支时消息列表正确切换，不混淆

#### Commits
- Commit A: feat(F079): conversation branching data model and UI
- Commit B: docs: mark F079 closed

---

### 任务 8：F110 图谱快照 URL 分享
**优先级**：P2
**估时**：2 天
**类型**：实施型
**依赖 LLM**：否
**审计来源**：[feature_audit_2026-05-17.md#f110--图谱快照与分享url-可分享快照](./feature_audit_2026-05-17.md#f110--图谱快照与分享url-可分享快照)

#### 背景
图谱页当前状态保存在 URL（`?nf=Tool&sn=xxx`），但完整的图谱视图状态（滤镜、缩放、高亮）没有可分享的快照机制。

#### 实现思路
- 编码：把当前 GraphFilterPanel state + zoom state + selected_node 编码成 base64 字符串
- 路由：`/graph?snapshot=<base64>` 加载时还原状态
- UI：图谱右上角加"复制分享链接"按钮

#### 验收
- [ ] 配置过滤器后点"分享"复制链接
- [ ] 另一标签页打开链接，恢复相同视图状态
- [ ] 链接 URL 长度可控（不超过 2KB）

#### Commits
- Commit A: feat(F110): graph snapshot URL share
- Commit B: docs: mark F110 closed

---

### 任务 9：F115 LLM 重试与熔断 ⚠️ GATED ON B001
**优先级**：P0
**估时**：1 天
**类型**：实施型 + 端到端验证依赖 LLM
**依赖 LLM**：是
**审计来源**：[feature_audit_2026-05-17.md#f115-llm-api-重试与熔断](./feature_audit_2026-05-17.md#f115-llm-api-重试与熔断)

⚠️ B001 未解除时：
- 可以写代码 + 单元测试（用 mock LLM 触发失败）
- 不能跑端到端（真 LLM 调用不通）

#### 背景
LLM 调用无重试机制，单次网络抖动或 Ollama 重启直接返回 500。需添加指数退避重试（≤ 3 次）和连续失败熔断（5 次失败 → 短路 60s）。注意：SSE 层已有的业务错误处理（`quota_exceeded` 等）不在此范围，熔断仅针对连接级错误。

#### 关键文件路径
- `backend/src/services/ai/llm_service.py` — `chat()` 方法加重试装饰器
- `backend/src/core/config.py` — `LLM_RETRY_MAX=3`, `LLM_CB_FAILURE_THRESHOLD=5`, `LLM_CB_TIMEOUT=60`

#### 实现思路
- 引入 `tenacity`：`@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))`
- 熔断计数写 Redis，连续失败 5 次后 60s 内直接抛 `CircuitOpenError` → 返回 503
- 熔断状态暴露至 `GET /api/health` 的响应体

#### 验收标准
- [ ] 停掉 Ollama，发查询 → 重试 3 次后返回 503（日志可见 3 次尝试）
- [ ] 连续触发熔断后，后续请求立即返回 503（不等重试超时）
- [ ] 重启 Ollama 后，60s 内自动恢复正常

#### 说明
如果 B001 仍然存在，端到端验证先跳过，保留 mock 单测结果即可。

#### Commits
- Commit A: feat(F115): llm retry and circuit breaker
- Commit B: docs: mark F115 closed

---

### 任务 10：F118 Embedding 批处理
**优先级**：P1
**估时**：1 天
**类型**：实施型性能优化
**依赖 LLM**：否（embedding 本地）
**审计来源**：[feature_audit_2026-05-17.md#f118-embedding-批处理](./feature_audit_2026-05-17.md#f118-embedding-批处理)

#### 背景
Embedding 服务逐条 encode，入库速度是主要瓶颈（bge-m3 CPU 模式尤甚）。改为批处理可充分利用矩阵运算，显著提升入库吞吐。

#### 步骤
1. 查看 `backend/src/services/ai/embedding_service.py`。
2. 将 `encode()` 改为 `encode_batch(texts: list[str])`。
3. 入库服务在 chunk 列表上批量调用，减少模型调用次数。
4. 将 `EMBEDDING_BATCH_SIZE` 写入 `settings`。
5. 用本地计时做批处理 vs 逐条对比。

#### 验收
- [ ] 入库 100 chunk 耗时相比逐条模式下降 ≥ 30%（本地计时对比）
- [ ] 批量结果与逐条结果 L2 距离 < 1e-5（精度不变）
- [ ] `EMBEDDING_BATCH_SIZE` 可通过 `.env` 调整

#### Commits
- Commit A: feat(F118): batch embedding encode path
- Commit B: docs: mark F118 closed

---

### 任务 11：F117 PDF 入库迁移 Celery
**优先级**：P2
**估时**：2-3 天
**类型**：架构层任务
**依赖 LLM**：否
**审计来源**：[feature_audit_2026-05-17.md#f117-异步任务队列](./feature_audit_2026-05-17.md#f117-异步任务队列)

⚠️ 此任务是子系统重构，按工作纪律 I4 必须停下来等用户。

#### 背景
PDF 入库同步阻塞（耗时 > 30s），HTTP worker 长期被占用。需将 `/api/ingest` 改为提交 Celery 任务后立即返回 `task_id`，实际处理异步执行，前端用现有轮询机制查询进度。

#### 关键文件路径
- `backend/src/routers/docs/upload.py` — 提交 Celery 任务，返回 202 + `task_id`
- `backend/src/tasks/ingest_task.py`（需新建）— 入库逻辑封装为 Celery task
- `backend/src/services/ingestion/processing_tracker.py` — 进度写入复用（已有）

#### 实现思路
- `upload.py`：保存临时文件 → `ingest_task.delay(filepath, task_id)` → 返回 202
- `ingest_task`：复用 `batch_ingest_service.py` 逻辑，写进度到 Redis
- 前端轮询逻辑不变，后端由同步改异步

#### 验收
- [ ] `POST /api/ingest` 立即返回 202 + `task_id`（< 1s）
- [ ] `GET /api/ingest/status/{task_id}` 轮询可见进度递增
- [ ] 任务失败时状态为 `failed`，前端可展示

#### Commits
- Commit A: feat(F117): move PDF ingest to Celery task
- Commit B: docs: mark F117 closed

---

### 任务 12：F122 全局长任务优雅关闭
**优先级**：P2
**估时**：1-2 周
**类型**：架构层大重构
**依赖 LLM**：否
**审计来源**：F116 调研发现

⚠️ 此任务是 F116 调研发现的，覆盖 17 处 fire-and-forget 任务。必须等用户决策三个选项才能开始。

#### 背景
SIGTERM 时，除了 SSE 流（F116 已覆盖），还有约 17 处 `asyncio.create_task()` 启动的后台长任务（PDF 入库、评测、GNN 训练、批量 OCR 等）。当前这些任务在 SIGTERM 时被直接 cancel，可能造成：
- PDF 入库中途崩，知识库状态不一致
- 评测任务部分结果丢失
- GNN 训练 checkpoint 未保存

#### 涉及位置
- `backend/src/routers/docs/ingest.py:230`
- `backend/src/routers/docs/entities.py:104`
- `backend/src/routers/docs/reprocess.py`
- `backend/src/routers/docs/images.py:205`
- `backend/src/services/ingestion/backfill_runtime.py:104`
- `backend/src/services/ingestion/batch_ingest_service.py`
- `backend/src/services/evaluation/*`
- `backend/src/routers/query/stream_agent.py:64`
- `backend/src/routers/graph_api/predict.py:52`
- `backend/src/routers/graph_api/gnn.py:109`
- `backend/src/services/quality/conflict_scan.py:97`

#### 设计选项
- 选项 A：每类任务自己实现 checkpoint + resume（工作量大但鲁棒）
- 选项 B：建一个全局 TaskRegistry，SIGTERM 时统一 cancel + 等待 N 秒（工作量中等，无 checkpoint 但有 grace）
- 选项 C：依赖 Celery 接管所有长任务（依赖 F117，彻底解决但属于大重构）

#### 验收
- [ ] SIGTERM 后 30s 内，正在跑的任务要么完成，要么保存了 checkpoint 可恢复，不能“中途消失”

#### Commits
- Commit A: feat(F122): global background task graceful shutdown
- Commit B: docs: mark F122 closed

---

### 任务 13：F039 前端 Vitest 测试补全
**优先级**：P2
**估时**：2 天
**类型**：测试基础设施
**依赖 LLM**：否
**审计来源**：[feature_audit_2026-05-17.md#f039--前端单元测试vitest](./feature_audit_2026-05-17.md#f039--前端单元测试vitest)

#### 背景
Vitest 框架已配置但测试覆盖率不足，需针对核心 Hook（`useStreamQuery`、`useConversation`）和工具函数补充单元测试。

#### 步骤
1. 查看现有 Vitest 配置和测试目录。
2. 为 `useStreamQuery` 补 SSE 解析 / 断线重连 / 错误归类测试。
3. 为 `useConversation` 和关键工具函数补充单测。
4. 维持测试风格与现有项目一致。
5. 验证 `pnpm test` 能跑通。

#### 验收
- [ ] `pnpm test` 通过，核心 Hook 覆盖率 ≥ 60%
- [ ] SSE 断线重连逻辑有测试覆盖

#### Commits
- Commit A: test(F039): add vitest coverage for core hooks and utils
- Commit B: docs: mark F039 closed

## 任务执行决策树

1. 先确认当前任务在 backlog 中是否仍为待办状态，且不属于已关闭条目。
2. 检查 `git status --short` 是否为空；若出现未跟踪文件，先解释来源再继续。
3. 每个任务必须遵守：实现 commit → 文档 commit → 工作区 clean → 才能进入下一任务。
4. 若任务涉及架构选择、数据模型改动、或明确要求用户决策（例如 F076 / F079 / F117 / F122），必须立刻停下来，等用户决定。
5. 若任务涉及 LLM 且 B001 仍未解除，优先做可验证的 mock / 单测部分，端到端验证暂停。
6. 若验证结果与代码逻辑不一致、出现副作用、或触发任何中断条件 I1-I10，立即停下并汇报。
