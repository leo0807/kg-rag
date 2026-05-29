# P1/P2 剩余任务执行清单（2026-05-17）

## 摘要
- 总任务数：15
- 已完成：8（F049、F060、F076、F110、F118、F120、F121、F031-pc）
- 待完成：7
- 估算工时：20.25 人天
- LLM 依赖任务（GATED ON B001）：2 条
- 当前 HEAD：c5b87e4

## 待执行任务（已决策）

按以下顺序执行，前一个 commit 落地 + 用户审核后才进下一个：

1. F117 PDF 入库 Celery（方案 B，前置验证）
2. F079 对话分支（方案 B + 形状 Y）
3. F122 全局长任务 Celery 化（BLOCKED ON F117）

总估时：7-12 人天

每个任务的详细决策见 [docs/dev_backlog_2026-05-17.md](./dev_backlog_2026-05-17.md) 对应条目的“决策记录”小节。

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

### F076 配置热重载（已闭环 ✓）
- commit: 7285e2e
- 验证：`.env` 修改触发 watcher 自动刷新；`POST /api/admin/config/reload` 手动刷新也能立即生效；仅白名单字段可热重载

### F120 PDF 解析异常优雅降级（已闭环 ✓）
- commit: 3ef822e
- 验证：`/api/preview` 对坏 PDF 返回 422 + 友好消息；真实 PDF 仍正常

### F121 多类型上传校验统一（已闭环 ✓）
- commit: f77418d
- 验证：`/api/preview` 6 项 + `/api/ingest` 6 项，共 12 项回归全过；`validate_upload()` 支持 `allowed_types` 白名单

### F110 图谱快照 URL 分享（已闭环 ✓）
- commit: 3163ade
- 验证：图谱页复制分享链接后可恢复过滤、选中节点与缩放状态；既有 `nf` / `sn` URL 同步已扩展为完整 snapshot 同步

### F118 Embedding 批处理（已闭环 ✓）
- commit: docs(F118): close as already-implemented after investigation
- 验证：code review 发现 `embed_batch(texts)` 已被所有 bulk path 调用，本地 bge-m3 直接走 `SentenceTransformer.encode(texts)`，原“逐条 encode 瓶颈”假设不成立

### F031-pc PC 端图片上传问答（已闭环 ✓）
- commits: 6b1b0fa, ae11335
- 验证：multipart `/api/query` 接口、图片上传 UI、预览、拖拽/粘贴/文件选择和历史会话回读均通过

## 完成记录表

| 任务 | 结果 | commit | 验证摘要 |
|---|---|---|---|
| F049 | CLOSED | 342dd5d | Tool/Material/Process/Constraint 独立颜色 + 过滤 + 详情侧栏 |
| F060 | CLOSED | 8495c1f, 948efd4 | tokenizer max_length 8192，单测 8/8 PASS |
| F076 | CLOSED | 7285e2e | `.env` watcher 自动刷新 + `POST /api/admin/config/reload` 手动刷新均生效 |
| F110 | CLOSED | 3163ade | 图谱快照 URL 可复制分享并恢复过滤、选中节点与缩放状态 |
| F118 | CLOSED | docs(F118): close as already-implemented after investigation | embed_batch(texts) 已覆盖所有 bulk path，bge-m3 走原生 batch encode |
| F031-pc | CLOSED | 6b1b0fa, ae11335 | multipart 上传、图片预览、拖拽/粘贴/文件选择和历史会话回读完成 |
| F022 | CLOSED | 328d23e | query/settings/graph 响应式入口与降级结构完成，浏览器 DOM 校验通过 |
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

**状态**：✅ 已闭环（2026-05-19）

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
- [x] 修改 `.env` 某配置项后 5 秒内无需重启即可读到新值

#### 完成记录
- commit: `7285e2e`
- 验证：`.env` 修改触发 watcher 自动刷新；`POST /api/admin/config/reload` 手动刷新也能立即生效
- 备注：仅白名单字段可热重载，DB / 端口 / JWT / LLM provider 仍保持不可热重载

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

**状态**：~~进行中~~ ✅ 已闭环

#### 背景
移动端图片提问 API 已实现，PC 端 query 页面原先无图片上传控件（无粘贴 / 点击上传）。现已补齐 PC 端 UI 与 multipart 路径，并完成历史回读验证。

#### 完成记录
- 2026-05-19：通过 multipart `/api/query` 扩展、图片上传 UI、历史会话回读验证，PC 端图片提问闭环。

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
- Commit A: feat(F031-be): /api/query accepts multipart with optional image
- Commit B: feat(F031-fe): add image upload UI and multipart send path
- Commit C: docs: mark F031-pc closed

⚠️ 此任务是新功能开发不是 bug 修复，按工作纪律 I4（架构层选择），"扩展 endpoint vs 新建 endpoint" 这个决策必须停下来等用户。

---

### 任务 6：F022 移动端响应式补齐
**优先级**：P2
**估时**：1 天
**类型**：实施型 UI
**依赖 LLM**：否
**审计来源**：[feature_audit_2026-05-17.md#f022--移动端适配](./feature_audit_2026-05-17.md#f022--移动端适配)

**状态**：✅ 已闭环

#### 背景
移动端基础布局已接入响应式入口，query/settings/graph 完成降级适配；登录页与深度图谱优化拆分为 F123 / F124。

#### 步骤
1. query 页接入移动侧栏抽屉，输入区保留发送与排队功能。
2. settings 页补移动端入口与纵向卡片布局。
3. graph 页采用降级布局：工具栏折行、详情侧栏降为底部面板。
4. 只调 Tailwind 类，不重写组件结构。
5. 浏览器 DOM 结构确认响应式入口与降级结构存在，桌面布局无回归。

#### 验收
- [ ] query 页移动端可用
- [ ] settings 页移动端可发现并打开
- [ ] graph 页移动端降级布局可访问
- [ ] 桌面视口（>= 1024px）行为不变

#### Commits
- Commit A: feat(F022): mobile responsive layout for query/settings/graph
- Commit B: docs(F022): mark F022 closed + update execution plan

#### 完成记录
- commit: 328d23e
- 验证：browser DOM 结构确认 query/settings/graph 的响应式入口与降级结构已接入；桌面布局未见回归

---

### 任务 7：F079 对话分支（已闭环 ✓）
**优先级**：P2
**估时**：1-2 天（实际 2026-05-25 一次推进完成）
**类型**：实施型新功能
**依赖 LLM**：否

#### 完成记录（2026-05-25）
形状 Y + 深拷贝 + 触发 C + 视图 Y 按决策记录全部实现。

#### 验收
- [x] 点击 user/assistant 消息的分支按钮，在新分支继续提问
- [x] ConversationSidebar 扁平列表显示派生标记（源对话 title + 第 N 条）
- [x] 分支独立深拷贝，互不影响（curl + psql 验证）
- [x] 源对话删除后分支保留（FK ON DELETE SET NULL 验证）
- [x] 单元测试 6/6 通过

#### Commits
- `e3f798f` feat(F079-schema): add branch_from columns to conversations
- `feff9f5` feat(F079-fk): backfill FK constraint for branch_from_conversation_id
- `9506cbe` feat(F079-be): POST /api/conversations/branch endpoint
- `4c0d661` feat(F079-fe): add branch button to user/assistant messages
- `ac89abe` feat(F079-sidebar): branch indicator in ConversationSidebar
- `d436dc6` test(F079): unit tests for branch endpoint

---

### 任务 8：F110 图谱快照 URL 分享（已闭环 ✓）
**优先级**：P2
**估时**：2 天
**类型**：实施型
**依赖 LLM**：否
**审计来源**：[feature_audit_2026-05-17.md#f110--图谱快照与分享url-可分享快照](./feature_audit_2026-05-17.md#f110--图谱快照与分享url-可分享快照)

**状态**：✅ 已闭环

#### 背景
图谱页当前状态保存在 URL（`?nf=Tool&sn=xxx`），但完整的图谱视图状态（滤镜、缩放、高亮）没有可分享的快照机制。

#### 实现思路
- 编码：把当前 GraphFilterPanel state + zoom state + selected_node 编码成 base64 字符串
- 路由：`/graph?snapshot=<base64>` 加载时还原状态
- UI：图谱右上角加"复制分享链接"按钮

#### 验收
- [x] 配置过滤器后点"分享"复制链接
- [x] 另一标签页打开链接，恢复相同视图状态
- [x] 链接 URL 长度可控（不超过 2KB）

#### 完成记录
- commit: `3163ade`
- 验证：图谱页可复制当前 snapshot URL，恢复过滤器、选中节点、缩放与渲染状态

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

### 任务 10：F118 Embedding 批处理（已闭环 ✓）
**优先级**：P1
**估时**：1 天
**类型**：实施型性能优化
**依赖 LLM**：否（embedding 本地）
**审计来源**：[feature_audit_2026-05-17.md#f118-embedding-批处理](./feature_audit_2026-05-17.md#f118-embedding-批处理)

#### 背景
调研发现 Embedding 服务已通过 `embed_batch(texts)` 覆盖所有 bulk path，bge-m3 本地实现直接使用 `SentenceTransformer.encode(texts)`。原本假设的“逐条 encode 瓶颈”并不存在。

#### 步骤
1. 查看 `backend/src/services/retrieval/embedding_service.py`。
2. 核对 `embed_batch(texts)` 是否被 bulk path 调用。
3. 核对本地 bge-m3 是否调用 `SentenceTransformer.encode(texts)`。
4. 记录调研结论，不做代码改动。

#### 验收
- [x] 入库批量路径已使用 `embed_batch(texts)`
- [x] 本地 bge-m3 已走原生 `SentenceTransformer.encode(texts)`
- [x] 原“逐条 encode 瓶颈”假设被证伪

#### 完成记录
- commit: `docs(F118): close as already-implemented after investigation`
- 验证：code review（`embedding_service.py` / `embedder.py` / `neo4j_writer.py` / `document_persistence.py` / `reprocess_vectorize.py`）
- 备注：F125/F126 已作为后续 P3 优化项记入 backlog

#### Commits
- Commit: `docs(F118): close as already-implemented after investigation`

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
**状态**：🟡 部分完成，3 子任务留尾（2026-05-30）
**类型**：架构层大重构
**依赖 LLM**：否
**审计来源**：F116 调研发现

#### 已完成
- graph_prediction、backfill、batch_ingest 均已 Celery 化（commits `3c1b6ec`, `39281f8`）
- health monitor 验证保留 asyncio（lifespan shutdown 已正确处理）

#### 留尾子任务（等用户决策优先级）
- **F122-A**（BLOCKED）：评测服务 5 处 + conflict_scan — 需先将进程内 `_tasks`/`_scans` dict 迁为 Redis 键，估时 2-3 天
- **F122-B gnn.py**（永久排除）：`get_gnn_service().reload()` 必须在 FastAPI 进程，不迁 Celery
- **F128 stream_agent**（独立追踪）：SSE 实时路径保留 asyncio；timeout/retry 作为独立需求

#### 验收（已通过）
- [x] SIGTERM 时 backfill/batch_ingest/graph_prediction 不会 mid-flight cancel
- [x] 11/11 unit tests pass

---

### 任务 13：F039 前端 Vitest 测试补全
**优先级**：P2
**估时**：2 天
**类型**：测试基础设施
**依赖 LLM**：否
**审计来源**：[feature_audit_2026-05-17.md#f039--前端单元测试vitest](./feature_audit_2026-05-17.md#f039--前端单元测试vitest)
**状态**：~~待开发~~ ✅ 已闭环 2026-05-19

#### 背景
Vitest 框架已配置，但原先只覆盖了极少量 API 工具函数。已围绕 `fetchApi`、`useStreamQuery` 错误归类、`MessageError`、`useKeyboard`、`ShortcutsModal` 补齐关键路径测试，并修正了 Vitest setup 配置。

#### 步骤
1. 查看现有 Vitest 配置和测试目录。
2. 为 `useStreamQuery` 补 SSE 解析 / 断线重连 / 错误归类测试。
3. 为 `MessageError`、`useKeyboard`、`ShortcutsModal` 补关键交互测试。
4. 维持测试风格与现有项目一致。
5. 验证 `pnpm vitest run` 能跑通。

#### 验收
- [x] `pnpm vitest run` 通过
- [x] 核心 Hook / 组件关键路径有守卫
- [x] SSE 断线重连逻辑有测试覆盖

#### 完成记录

| 任务 | 结果 | commit | 验证摘要 |
|---|---|---|---|
| F039 | CLOSED |  | `pnpm vitest run` 通过，5 个测试文件共 22 个测试全绿 |

#### Commits
- Commit A: test(F039): add vitest coverage for core hooks and utils
- Commit B: docs(F039): mark F039 closed + update execution plan

## 任务执行决策树

1. 先确认当前任务在 backlog 中是否仍为待办状态，且不属于已关闭条目。
2. 检查 `git status --short` 是否为空；若出现未跟踪文件，先解释来源再继续。
3. 每个任务必须遵守：实现 commit → 文档 commit → 工作区 clean → 才能进入下一任务。
4. 若任务涉及架构选择、数据模型改动、或明确要求用户决策（例如 F076 / F079 / F117 / F122），必须立刻停下来，等用户决定。
5. 若任务涉及 LLM 且 B001 仍未解除，优先做可验证的 mock / 单测部分，端到端验证暂停。
6. 若验证结果与代码逻辑不一致、出现副作用、或触发任何中断条件 I1-I10，立即停下并汇报。
