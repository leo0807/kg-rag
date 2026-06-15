# Help Drawer 手动测试清单（Batch 0）

浏览器实测前确认代码已构建并在 dev 模式运行（`npm run dev`）。
逐项勾选，所有步骤通过后 Batch 0 测试完成。

---

## 步骤 1：帮助按钮可见性

**目标**：每个已登录页面的右下角都能看到帮助按钮。

- [ ] 导航至 `/query`，确认右下角出现帮助按钮（问号图标）
- [ ] 导航至 `/library`，确认帮助按钮存在
- [ ] 导航至 `/admin/dashboard`，确认帮助按钮存在
- [ ] 导航至 `/login`，**确认帮助按钮不存在**（`/login` 在 `NO_SIDEBAR_PATHS` 中，不渲染 `HelpDrawer`）

---

## 步骤 2：首次打开行为（pulse 动画 + localStorage）

**目标**：首次访问某路由时，按钮显示脉冲动画；点击后动画消失且 localStorage 记录已读状态。

- [ ] 清除 `localStorage`（F12 → Application → Local Storage → 删除 `help_pulsed_v1`）
- [ ] 导航至 `/query`，确认帮助按钮有 `animate-pulse` 脉冲动画
- [ ] 点击帮助按钮打开抽屉，再关闭
- [ ] 确认 `localStorage.getItem("help_pulsed_v1")` 中包含 `/query` 的 key
- [ ] 再次打开同一页面，确认脉冲动画**不再出现**

---

## 步骤 3：抽屉开关交互

**目标**：点击帮助按钮打开抽屉，点击关闭按钮或遮罩关闭抽屉；移动端遮罩层级正确。

- [ ] 点击帮助按钮 → 确认抽屉从右侧滑入（`fixed inset-y-0 right-0 z-40 w-full md:w-80`）
- [ ] 点击抽屉内的 × 关闭按钮 → 确认抽屉收起
- [ ] 再次打开抽屉 → 在移动端视口（< 768px）点击左侧遮罩 → 确认抽屉关闭
- [ ] 确认抽屉打开时**不遮挡** ExportMenu 的 toast（ExportMenu 使用 `z-50`，高于抽屉 `z-40`）

---

## 步骤 4：路由切换时内容更新

**目标**：从页面 A 导航至页面 B，抽屉内容自动切换至 B 的帮助指南。

- [ ] 在 `/query` 打开帮助抽屉，确认标题为「知识问答」
- [ ] 不关闭抽屉，直接通过侧边栏导航至 `/library`
- [ ] 确认抽屉标题更新为「文档库」，内容切换正确
- [ ] 导航至 `/admin/dashboard`，确认抽屉标题更新为「系统健康看板」

---

## 步骤 5：路由交叉污染检查（静态 vs 动态路由）

**目标**：同前缀的静态路由不会被动态正则「吞掉」；动态路由正确匹配。

| 测试路由                | 预期标题                  | 实际标题 |
|------------------------|--------------------------|---------|
| `/simulation`          | 仿真案例库                |         |
| `/simulation/compare`  | 仿真对比                  |         |
| `/simulation/dashboard`| 仿真仪表盘                |         |
| `/simulation/CASE-001` | 仿真案例详情              |         |
| `/generation`          | 文档生成任务              |         |
| `/generation/new`      | 新建生成任务              |         |
| `/generation/abc123`   | 生成任务进度              |         |
| `/generation/abc123/edit` | 生成任务编辑           |         |
| `/admin/eval`          | 评测中心                  |         |
| `/admin/eval/datasets` | 评测数据集                |         |
| `/admin/eval/runs/RUN-001` | 评测运行详情          |         |
| `/library`             | 文档库                    |         |
| `/library/DOC-001`     | 文档详情                  |         |
| `/wiki`                | 规范 Wiki                 |         |
| `/wiki/SPEC-001`       | 规范详情                  |         |

- [ ] 逐行填写「实际标题」列，确认全部与预期一致

---

## 步骤 6：重定向路由验证

**目标**：服务端/客户端重定向路由最终落在正确页面，帮助抽屉内容与落点一致。

- [ ] 访问 `/`（服务端重定向 → `/ingest` → `/library`）
  - 最终页面：`/library`，帮助标题应为「文档库」
- [ ] 访问 `/ingest`（客户端重定向 → `/library`）
  - 最终页面：`/library`，帮助标题应为「文档库」
- [ ] 访问 `/graph/builder`（服务端重定向 → `/cypher?tab=builder`）
  - 最终页面：`/cypher`，帮助标题应为「Cypher 查询」
- [ ] 访问 `/admin/cypher`（服务端重定向 → `/cypher?tab=admin`）
  - 最终页面：`/cypher`，帮助标题应为「Cypher 查询」

---

## 测试结果汇总

| 步骤 | 描述              | 结果 |
|------|------------------|------|
| 1    | 按钮可见性        |      |
| 2    | pulse 动画与 localStorage |  |
| 3    | 抽屉开关交互      |      |
| 4    | 路由切换内容更新  |      |
| 5    | 路由交叉污染      |      |
| 6    | 重定向路由落点    |      |

**全部通过后在此注明日期与测试人，提交 QA 记录。**
