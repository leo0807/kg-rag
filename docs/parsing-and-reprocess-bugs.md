# 文档解析与重处理 Bug 记录

本文档记录了在开发过程中发现的文档解析与重处理功能 Bug，包括根本原因分析和修复方案，供后续维护参考。

---

## 一、PDF 章节正则匹配问题

### 1.1 `°`（度符号）导致章节漏识别

**受影响文档**：CPS0200 等含温度/角度规格章节的 PDF

**现象**：章节 `6.2.5 常温180°剥离强度要求` 未被解析，导致该章节内容丢失。

**根本原因**：

`SECTION_PATTERN` 的标题体字符类不包含 `°`（U+00B0，度符号）。正则在遇到 `°` 时停止匹配，整行无法通过模式验证，章节被跳过。

```python
# 旧字符类（不含 °）
r'[\u4e00-\u9fff\u3400-\u4dbf\uff00-\uffefA-Za-z0-9（）、，。：；·— \t]{0,50}'
```

**修复方案**：

在字符类末尾加入 `/°`：

```python
# 新字符类（含 / 和 °）
r'[\u4e00-\u9fff\u3400-\u4dbf\uff00-\uffefA-Za-z0-9（）、，。：；·— \t/°]{0,50}'
```

**涉及文件**：
- `backend/src/services/parser.py`：`SECTION_PATTERN`
- `backend/src/services/docx_parser.py`：`_NUM_RE`

---

### 1.2 `/`（正斜杠）导致含斜杠章节标题漏识别

**受影响文档**：CPS3200 等含 `制造程序/说明` 类章节的 PDF

**现象**：章节 `7 制造程序/说明` 未被解析，导致第 7 章整体缺失。

**根本原因**：与 1.1 相同——字符类不含 `/`，遇到斜杠时匹配失败。

**修复方案**：同 1.1，将 `/` 加入字符类（与 `°` 一并修复）。

---

### 1.3 `\s` 匹配换行符导致跨行错误匹配

**现象**：部分章节标题被错误识别，内容混入下一章节开头的文字。

**根本原因**：

早期修复将标题体字符类写为 `[\u4e00-\u9fff\w\s\/\-]`，其中 `\s` 包含 `\n`。即使使用 `re.MULTILINE`，字符类中的 `\s` 仍然能跨行匹配，使正则一次吸收多行内容。

```python
# 问题代码（\s 含换行）
r'([\u4e00-\u9fff\w\s\/\-]+)'
```

**修复方案**：将 `\s` 替换为 `[ \t]`（仅匹配空格和制表符，不含换行）：

```python
r'[\u4e00-\u9fff\u3400-\u4dbf\uff00-\uffefA-Za-z0-9（）、，。：；·— \t/°]{0,50}'
```

---

### 1.4 表格行数字被误识别为章节标题（假阳性）

**现象**：类似 `1 外观 I型：目视观察无发泡、不脆 6.2.2` 的表格行被识别为章节。

**根本原因**：

宽松的正则允许行内出现测量符号（`≥ ≤ ± % °`）、连接词（`I型`）和行末引用号（`6.2.2`），导致表格单元格行被误判。

**修复方案**：

1. **严格字符类**：排除 `%`、`≥`、`≤`、`±` 等测量符号，使表格数据行无法通过。
2. **尾部负向后行断言** `(?<!\d)$`：章节号必须不以数字结尾，排除 `... 6.2.2` 类的引用行。
3. **过滤器后置校验**：

```python
matches = [m for m in matches
           if len(m.group(2).strip()) >= 2
           and m.group(2).strip() != '_'
           and not m.group(2).strip().replace('.', '').replace(' ', '').isdigit()]
```

---

### 1.5 最终 SECTION_PATTERN（当前版本）

```python
SECTION_PATTERN = re.compile(
    r'^(\d{1,2}(?:\.\d{1,2}){0,3})[ \t]+'
    r'([\u4e00-\u9fff\u3400-\u4dbfA-Za-z]'
    r'[\u4e00-\u9fff\u3400-\u4dbf\uff00-\uffefA-Za-z0-9（）、，。：；·— \t/°]{0,50})'
    r'(?<![ \t])(?<!\d)$',
    re.MULTILINE
)
```

设计规则说明：

| 规则 | 目的 |
|------|------|
| `^` + `re.MULTILINE` | 每行独立匹配，避免跨行 |
| `[ \t]+` 而非 `\s+` | 章节号与标题之间只允许空格/制表符，禁止换行 |
| 首字必须为汉字或 ASCII 字母 | 排除以数字/符号开头的表格行 |
| 字符类限定（无 `%≥≤±`） | 排除测量值行 |
| `(?<!\d)$` | 排除以数字结尾的行（章节引用、表格序号） |
| 后置 isdigit 过滤 | 兜底过滤纯数字伪章节 |

---

## 二、重处理任务卡死问题

### 2.1 单文档任务永久挂起（status 停在 "pending"）

**现象**：点击重处理后，前端状态一直显示"排队中"，永不执行。

**根本原因**：

`asyncio.create_task()` 不传播异常——任务协程内的 `import` 失败或其他异常会被静默丢弃，`task` 字典的 `status` 字段从未更新，前端轮询永远拿到 `pending`。

```python
# 旧代码（异常被吞掉）
async def _run():
    from ..services.reprocess_service import reprocess_document
    await asyncio.to_thread(reprocess_document, doc_id, driver, pipelines, task)

asyncio.create_task(_run())
```

**修复方案**：

在协程内加 try/except，确保异常更新 `task` 状态：

```python
async def _run():
    try:
        from ..services.reprocess_service import reprocess_document
        await asyncio.to_thread(reprocess_document, doc_id, driver, pipelines, task)
    except Exception as e:
        task.update({"status": "failed", "error": str(e),
                     "finished_at": int(time.time())})
        logger.error("[reprocess %s] 任务协程异常: %s", doc_id, e)
```

---

### 2.2 批量重处理永远停在"排队中"

**现象**：批量重处理任务触发后，前端一直显示"排队中"，实际上无任何文档被处理。

**根本原因**：

原实现依赖 Celery Worker 进程执行批量任务。部署环境中未启动独立的 Celery Worker 进程，任务提交到 Redis 队列后无人消费，永远处于 PENDING 状态。

**修复方案**：

移除 Celery/Redis 依赖，改为在 FastAPI 进程内用 `asyncio.create_task()` + `asyncio.to_thread()` 执行批量任务：

```python
# _run_batch 是普通 async 协程，在事件循环内逐文档顺序执行
async def _run_batch(doc_ids: list[str], pipelines: list[str]) -> None:
    for doc_id in doc_ids:
        if _batch.get("cancel_requested"):
            break
        await asyncio.to_thread(reprocess_document, doc_id, driver, pipelines, task_proxy)
        done += 1

asyncio.create_task(_run_batch(doc_ids, pipelines))
```

**涉及文件**：`backend/src/routers/reprocess.py`

---

## 三、文件查找失败（重解析找不到原文件）

### 3.1 `find_pdf()` 仅搜索 `uploads/`，漏掉 `uploads/docs/`

**现象**：reparse 管道日志显示"未找到 PDF 文件，跳过"，重解析结果为 0 章节。

**根本原因**：

新版上传接口将文件存入 `uploads/docs/`，而旧版 `find_pdf()` 仅搜索 `uploads/` 根目录。

**修复方案**：

```python
UPLOAD_DIR     = Path("uploads")
DOC_UPLOAD_DIR = Path("uploads") / "docs"

def find_pdf(doc_id: str) -> Path | None:
    exts = ["pdf", "PDF", "docx", "DOCX", "doc", "DOC"]
    for base in (DOC_UPLOAD_DIR, UPLOAD_DIR):   # 先搜新目录
        for ext in exts:
            candidates = sorted(base.glob(f"{doc_id}*.{ext}"))
            if candidates:
                return candidates[0]
    return None
```

**涉及文件**：`backend/src/services/reprocess_service.py`

---

## 四、表格提取失败

### 4.1 PP-Structure / PaddleOCR 未安装时静默返回 0

**现象**：表格提取管道显示失败或结果为 0，日志无明显报错。

**根本原因**：

表格提取依赖 PaddleOCR 的 PP-Structure 组件（`paddleocr`、`fitz`）。`is_struct_available()` 检查这两个包是否已安装：

```python
def is_struct_available() -> bool:
    return _PADDLE_AVAILABLE and _FITZ_AVAILABLE
```

若未安装，`extract_all_tables()` 直接返回空列表，不抛异常，前端仅看到结果为 0。

**解决方法**：

这是预期行为（可选依赖降级）。若需要表格提取功能，需在服务器上安装：

```bash
pip install paddlepaddle paddleocr pymupdf
```

安装完成后重启后端，`is_struct_available()` 将返回 `True`，表格提取自动启用。

**涉及文件**：`backend/src/services/table_extractor.py`、`backend/src/services/ocr_engine.py`

---

## 五、前端重处理页面进入即自动执行

**现象**：打开文档详情页的重处理面板时，立刻触发一次重处理请求。

**根本原因**：

`ReprocessPanel.tsx` 中 `useEffect` 依赖数组配置不当（或组件挂载时直接调用了 `handleStart()`），导致组件挂载时自动发出 POST 请求。

**修复方案**：

将触发逻辑改为仅在用户主动点击"开始"按钮时执行，`useEffect` 只用于状态轮询：

```tsx
// 只在 status === "running" 时启动轮询
useEffect(() => {
    if (status !== "running") return;
    const timer = setInterval(fetchStatus, 2000);
    return () => clearInterval(timer);
}, [status]);
```

**涉及文件**：`frontend/src/app/library/[doc_id]/ReprocessPanel.tsx`

---

---

## 六、批量处理进度切换 Tab 后消失

**现象**：批量任务运行中，切换到"文档列表"再切回"重新处理"，进度面板短暂显示空白或 idle 状态。完成后重新进入该 Tab，也看不到章节数目更新。

**根本原因**：

`LibraryReprocessTab` 以 `{activeTab === "reprocess" && <LibraryReprocessTab />}` 方式条件渲染，切换 Tab 时组件会完全卸载（unmount），React state 全部清空。重新挂载时 `batch` 从 `{ status: "idle" }` 开始，需等待异步 fetch 才能还原为实际状态，期间进度面板显示空。

此外，文档列表（`docs` 状态）只在组件挂载时加载一次，批量完成后章节数目不刷新。

**修复方案**：

1. **`sessionStorage` 持久化**：每次更新 `batch` 状态时同步写入 `sessionStorage`，组件重新挂载时从 `sessionStorage` 读取初始值，消除闪烁。
2. **监听 `batch.status === "completed"` 重新拉取文档列表**：

```tsx
// 初始化时从 sessionStorage 读取
const [batch, setBatch] = useState<Batch>(() => {
    try {
        const stored = sessionStorage.getItem("kg_batch_status");
        return stored ? JSON.parse(stored) : { status: "idle" };
    } catch { return { status: "idle" }; }
});

// 统一更新函数，同步写 sessionStorage
function updateBatch(next: Batch | ((prev: Batch) => Batch)) {
    setBatch(prev => {
        const val = typeof next === "function" ? next(prev) : next;
        try { sessionStorage.setItem("kg_batch_status", JSON.stringify(val)); } catch {}
        return val;
    });
}

// 完成后刷新文档列表（章节数目更新）
useEffect(() => {
    if (batch.status === "completed") fetchDocs();
}, [batch.status]);
```

**涉及文件**：`frontend/src/app/library/LibraryReprocessTab.tsx`

---

## 七、刷新页面后 Tab 回到默认位置

**现象**：在"文档库"的"重新处理"Tab 或"导入文件"Tab，或文档详情的"工程图纸"/"重新处理"Tab 刷新页面后，总是回到默认 Tab。

**根本原因**：

两处 Tab 状态均使用 React `useState`（纯内存），不编码到 URL，刷新时状态丢失：

```tsx
// library/page.tsx
const [activeTab, setActiveTab] = useState<"list" | "ingest" | "reprocess">("list");

// DocumentDetailClient.tsx
const [activeTab, setActiveTab] = useState<"sections" | "drawings" | "reprocess">("sections");
```

**修复方案**：

使用 URL hash 持久化 Tab 状态。Hash 变更不触发页面跳转，且刷新后由浏览器保留：

```tsx
// 挂载时从 hash 恢复
useEffect(() => {
    const hash = window.location.hash.slice(1);
    if (hash === "ingest" || hash === "reprocess") setActiveTab(hash);
}, []);

// 切换时同步更新 hash
function switchTab(tab: "list" | "ingest" | "reprocess") {
    setActiveTab(tab);
    history.replaceState(null, "",
        tab === "list" ? window.location.pathname : `${window.location.pathname}#${tab}`
    );
}
```

**涉及文件**：
- `frontend/src/app/library/page.tsx`
- `frontend/src/app/library/[doc_id]/DocumentDetailClient.tsx`

---

## 八、"60" 章节号误识别根本原因分析

**现象**：CPS0203 等文档数据库中出现章节号 "60"，同时部分真实章节（如 6.4.2.1–6.4.2.10）缺失。

**根本原因**：

原 `SECTION_PATTERN` 使用 `\s+` 连接章节号与标题：

```python
r'^(\d{1,2}(?:\.\d{1,2}){0,2})\s+([\u4e00-\u9fff\w\/\-]+)'
```

`re.MULTILINE` 使 `^` 匹配每行行首，但 **`\s+` 包含 `\n`**，即字符类中的 `\n` 在 MULTILINE 模式下仍然生效。当 PDF 某页页码被 pdfplumber 提取在独立一行（如 `60\n材料控制要求...`），正则将 `60` + 换行 + 下一行内容匹配为 "60 章节材料控制要求"，产生假阳性；同时由于字符集太窄，`6.4.2.1` 等细分章节被漏识别。

**修复**：

- 将分隔符 `\s+` 改为 `[ \t]+`（仅允许行内空白，不含换行）
- 扩展标题字符类，加入 `/`、`°` 等工程文档常用符号
- 加 `(?<!\d)$` 负向后行断言，排除以数字引用结尾的表格行

**重要说明**：此 Bug 修复后，**数据库中的历史错误数据需通过重新处理（reparse 管道）才能清除**。

---

---

## 九、批量重处理文档数量上限（per_page=500）

**现象**：重新处理页面只显示 500 个文档，实际已上传 558 个文档，多余的 58 个无法被选入批量处理。

**根本原因**：

`LibraryReprocessTab.tsx` 中硬编码了 `per_page=500`：

```javascript
fetch("/api/documents?per_page=500", { headers: h })
```

`/api/documents` 端点直接将 `per_page` 传给 Neo4j LIMIT，无服务端上限限制。当文档数量超过 500 时，超出部分被截断。

**修复方案**：

改为分页全量拉取：先请求第 1 页获取 `pages` 字段，再并发拉取剩余页：

```javascript
async function fetchDocs() {
    const PER = 500;
    const first = await fetch(`/api/documents?per_page=${PER}&page=1`, { headers: h }).then(r => r.json());
    let all = first.data ?? [];
    const pages = first.pages ?? 1;
    if (pages > 1) {
        const rest = await Promise.all(
            Array.from({ length: pages - 1 }, (_, i) =>
                fetch(`/api/documents?per_page=${PER}&page=${i + 2}`, { headers: h }).then(r => r.json())
            )
        );
        for (const d of rest) all = all.concat(d.data ?? []);
    }
    setDocs(all);
}
```

**涉及文件**：`frontend/src/app/library/LibraryReprocessTab.tsx`

---

## 十、批量处理进度条不可见（0% 时蓝色填充宽度为零）

**现象**：批量任务启动后，进度面板存在（有灰色容器）但看不到任何蓝色进度，像没有显示一样。

**根本原因**：

进度条使用 `width: ${progress}%`。处理 558 个文档时，第一个文档完成前 `done = 0`，`progress = 0`，蓝色填充宽度为 0px，视觉上与空状态无异。首个文档完成后才出现 0.18% 的细线，几乎不可见。

此外，进度计算对 `batch.total` 没有防空值保护：若 sessionStorage 中的 batch 对象缺少 `total` 字段，会导致 `progress = 0` 且文本显示 "0 / — 个文档"。

**修复方案**：

1. 当 `isRunning && progress === 0` 时改用脉冲动画（indeterminate），让用户知道任务正在运行：
```jsx
{isRunning && progress === 0 ? (
    <div className="h-full w-full bg-indigo-500/50 animate-pulse rounded-full" />
) : (
    <div style={{ width: `${progress}%`, minWidth: progress > 0 ? "6px" : "0" }} />
)}
```
2. 增加双层进度条：总文档进度（done/total）+ 当前文档内管道进度（current_step / pipelines.length）
3. 增加后台运行提示文字，告知用户关闭浏览器后任务仍在运行

**涉及文件**：`frontend/src/app/library/LibraryReprocessTab.tsx`

---

## 十一、服务重启后批量任务状态丢失

**现象**：管理员启动批量处理后，服务器重启（容器重启/OOM 重启等），`_batch` 内存状态清空，原本已处理完的文档列表丢失，无法从断点续跑。

**根本原因**：

`_batch` 是 Python 模块级字典，完全在内存中，服务进程重启后归零。

**修复方案**：

1. 模块加载时从 `batch_state.json` 恢复状态：
```python
def _load_batch_state() -> dict:
    if _BATCH_STATE_FILE.exists():
        state = json.loads(_BATCH_STATE_FILE.read_text())
        if state.get("status") == "running":
            state["status"] = "interrupted"   # 进程已不在，不可能还在跑
        return state
    return {"status": "idle"}

_batch = _load_batch_state()
```
2. 每完成一个文档后调用 `_save_batch_state()` 写入文件，保存 `completed_docs` 等断点信息
3. 启动 / 续跑 / 清除时也同步写文件
4. 前端新增 `interrupted` 状态（黄色标签 + 显示"已中断，可续跑"）

**涉及文件**：`backend/src/routers/reprocess.py`（新增 `_BATCH_STATE_FILE`、`_load_batch_state()`、`_save_batch_state()`）

---

## 十二、文档解析验证功能设计

### 功能目标

在无需人工逐篇检查的情况下，自动发现可能解析有误的文档（空章节、0章节、标题丢失等），优先提交这些文档进行 reparse。

### 验证规则体系

| 级别 | 代码 | 规则描述 |
|------|------|----------|
| Error | E001 | 文档 title 为空 |
| Error | E002 | doc_id 为空 |
| Error | E003 | 章节数为 0 |
| Warning | W001 | doc_id 不匹配 `CPS\d+` 格式 |
| Warning | W002 | 章节数 < 3（解析可能不完整）|
| Warning | W003 | 某章节 content 为空或极短（< 10 字符）|
| Warning | W004 | 顶级章节编号跳跃（如 1→3，缺少 2）|
| Warning | W005 | 章节编号重复 |
| Warning | W006 | 章节标题超过 60 字（正文误识别为标题）|
| Info | I001 | 平均章节内容 < 100 字（OCR 质量可能偏低）|

### 评分方式

`score = max(0, 100 - Σ扣分)`，Error 扣 25 分，Warning 扣 8 分，Info 扣 2 分。score ≥ 80 且无 Error 视为验证通过。

### 接口设计

```
GET /api/documents/{doc_id}/validate    # 单文档验证
GET /api/documents/validate-all         # 批量验证（返回汇总统计 + 各文档报告）
```

### 前端集成

在文档详情的"重新处理"面板内增加"验证解析质量"折叠区块：点击后实时调用 API，展示分数徽章、统计数字（章节数/空章节/平均字数）及问题列表（错误用红色叉号、警告用黄色三角、信息用蓝色 i）。

**涉及文件**：
- `backend/src/services/validator.py`（新建）
- `backend/src/routers/documents.py`（新增两个 GET 端点）
- `frontend/src/app/library/[doc_id]/ReprocessPanel.tsx`（新增验证区块）

---

## 十三、修改汇总

| 文件 | 修改内容 |
|------|----------|
| `backend/src/services/parser.py` | SECTION_PATTERN：字符类加入 `/°`，将 `\s` 改为 `[ \t]`，加 `(?<!\d)$` 负向断言 |
| `backend/src/services/docx_parser.py` | `_NUM_RE`：同上 |
| `backend/src/services/reprocess_service.py` | `find_pdf()` 双目录搜索；新增 `_run_reparse()` 管道 |
| `backend/src/services/neo4j_writer.py` | 新增 `rewrite_sections()`：清理旧 Section 节点，重建图谱 + Milvus + ES |
| `backend/src/services/milvus_store.py` | 新增 `delete_by_doc_id()`：按文档 ID 删除向量 |
| `backend/src/services/validator.py` | **新建**：10 条验证规则 + 0-100 评分 + 批量验证汇总 |
| `backend/src/routers/reprocess.py` | 移除 Celery；asyncio 任务；`_batch` 持久化到 `batch_state.json`；新增 `/clear` 端点 |
| `backend/src/routers/documents.py` | 新增 `GET /documents/{doc_id}/validate` 和 `GET /documents/validate-all` |
| `frontend/src/app/library/[doc_id]/ReprocessPanel.tsx` | 修复自动执行；reparse 管道；新增验证面板 |
| `frontend/src/app/library/LibraryReprocessTab.tsx` | 分页全量拉取文档；双层进度条 + 脉冲动画；sessionStorage 持久化；完成后刷新章节数；`interrupted` 状态支持 |
| `frontend/src/app/library/page.tsx` | URL hash 持久化 Tab 状态 |
| `frontend/src/app/library/[doc_id]/DocumentDetailClient.tsx` | URL hash 持久化 Tab 状态 |
