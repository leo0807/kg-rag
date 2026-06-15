import type { GuideEntry } from "./types";

export const generationGuides: GuideEntry[] = [
  {
    match: "/generation",
    key: "/generation",
    guide: {
      title: "文档生成任务",
      summary: "查看与管理所有文档生成任务列表。",
      features: [
        // 依据: generation/page.tsx L?, GET /api/generation/tasks + filter status
        "任务列表（GET /api/generation/tasks，支持状态过滤）",
        // 依据: 6 filter tabs: all/pending/running/done/finalized/failed
        "6 个状态过滤标签：全部 / 待处理 / 运行中 / 完成 / 已定稿 / 失败",
        // 依据: TaskCard: status badge, progress bar (if running), validation score
        "任务卡片：状态徽章、运行中进度条与验证评分",
        // 依据: Link: done/finalized → /generation/[id]/edit; others → /generation/[id]
        "完成/定稿任务跳转至编辑页，其余跳转至进度页",
        // 依据: DELETE /api/generation/tasks/[id]
        "删除任务（DELETE /api/generation/tasks/[id]）",
      ],
      actions: [
        "点击标签页按状态过滤任务列表。",
        "点击任务卡片跳转至进度详情或编辑页。",
        "点击删除图标移除指定任务。",
        "点击「新建任务」按钮进入 5 步向导。",
      ],
      related: [
        { label: "新建生成任务", href: "/generation/new" },
        { label: "文档库", href: "/library" },
      ],
    },
  },

  {
    match: "/generation/new",
    key: "/generation/new",
    guide: {
      title: "新建生成任务",
      summary: "通过 5 步向导配置并启动文档生成。",
      features: [
        // 依据: generation/new/page.tsx L?, STEPS = ["选择模板","基本信息","参考规范","试验数据","确认启动"]
        "5 步向导：选择模板 → 基本信息 → 参考规范 → 试验数据 → 确认启动",
        // 依据: WizardStepper, TemplateSelector, ReferenceDocPicker components
        "步骤组件：WizardStepper / TemplateSelector / ReferenceDocPicker",
        // 依据: POST /api/generation/tasks to create
        "提交创建（POST /api/generation/tasks）",
      ],
      actions: [
        "依次填写每个步骤的配置内容，点击「下一步」推进。",
        "在「选择模板」步骤选择文档类型模板。",
        "在「参考规范」步骤选取相关知识库文档作为参考。",
        "在「确认启动」步骤确认配置后提交，跳转至任务列表。",
      ],
      related: [
        { label: "生成任务列表", href: "/generation" },
        { label: "文档库", href: "/library" },
      ],
    },
  },

  {
    match: "/settings",
    key: "/settings",
    guide: {
      title: "个人设置",
      summary: "管理个人信息、密码、模型与系统偏好。",
      features: [
        // 依据: settings/page.tsx, Tabs: profile, password, model, preferences + admin-only: admin, audit, search, entity_filter, alert
        "普通标签页：个人资料 / 密码 / 模型 / 偏好设置",
        "管理员专属标签：用户管理 / 审计 / 搜索 / 实体过滤 / 告警",
        // 依据: ProfileTab, PasswordTab, ModelTab, PreferencesTab, AdminTab, AuditTab, SearchTab, EntityFilterTab, AlertTab
        "各标签对应独立 Tab 组件（Profile/Password/Model/Preferences/...）",
        // 依据: isAdmin from localStorage
        "管理员标签按 localStorage isAdmin 字段控制显示",
      ],
      actions: [
        "切换标签页修改对应配置，点击保存按钮生效。",
        "在「模型」标签页选择默认使用的 AI 模型。",
        "在「偏好」标签页调整界面与通知偏好。",
        "管理员可在专属标签页管理用户、审计日志与告警规则。",
      ],
      related: [
        { label: "通知中心", href: "/notifications" },
        { label: "开发者 API", href: "/developers" },
      ],
    },
  },

  {
    match: "/developers",
    key: "/developers",
    guide: {
      title: "开发者中心",
      summary: "管理 API 密钥并查看接口使用示例。",
      features: [
        // 依据: developers/page.tsx, Tabs: keys/docs/history
        "3 个标签页：API 密钥 / 接口文档 / 调用历史",
        // 依据: GET/POST /api/admin/api-keys, DELETE /api/admin/api-keys/[id]
        "API 密钥 CRUD（GET/POST /api/admin/api-keys，DELETE /[id]）",
        // 依据: Scopes: query:read/documents:read/feedback:write/admin:read
        "密钥权限范围：query:read / documents:read / feedback:write / admin:read",
        // 依据: Code examples shown in CodeBlock component with curl/Python
        "代码示例（curl / Python，CodeBlock 组件）",
      ],
      actions: [
        "点击「新建密钥」填写名称和权限范围，复制保存生成的 Key。",
        "切换至「接口文档」标签查看 curl / Python 调用示例。",
        "切换至「调用历史」标签查看 API 使用记录。",
        "点击密钥旁的删除图标撤销对应密钥。",
      ],
      related: [
        { label: "个人设置", href: "/settings" },
        { label: "凭证管理", href: "/admin/credentials" },
      ],
    },
  },

  {
    match: "/notifications",
    key: "/notifications",
    guide: {
      title: "通知中心",
      summary: "查看并管理系统推送的各类通知消息。",
      features: [
        // 依据: notifications/page.tsx, MOCK data (no API call yet)
        "通知列表（当前使用 MOCK 数据，API 待接入）",
        // 依据: Filter: all/unread
        "全部 / 未读 两种过滤视图",
        // 依据: markRead(id), markAllRead()
        "标记单条已读（markRead）与全部已读（markAllRead）",
        // 依据: TYPE_COLOR: answer.created/evaluation.completed/alert.triggered/quota.exceeded/document.uploaded
        "通知类型：答案生成 / 评测完成 / 告警触发 / 配额超限 / 文档上传",
      ],
      actions: [
        "切换「未读」视图只显示未读通知。",
        "点击单条通知标记已读。",
        "点击「全部已读」一键清除未读状态。",
      ],
      related: [
        { label: "个人设置", href: "/settings" },
        { label: "系统告警", href: "/admin/status" },
      ],
    },
  },
];
