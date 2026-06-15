import type { GuideEntry } from "./types";

export const adminSecurityGuides: GuideEntry[] = [
  {
    match: "/admin/compliance",
    key: "/admin/compliance",
    guide: {
      title: "等保合规仪表盘",
      summary: "等保 2.0 合规评分与失败项分类展示。",
      features: [
        // 依据: admin/compliance/page.tsx L137, GET /api/admin/security/compliance (auto-runs on mount)
        "合规检测自动触发（GET /api/admin/security/compliance，页面加载即运行）",
        // 依据: Title "等保2.0 合规仪表盘", overall_score, failed_critical count
        "整体评分与关键失败项计数",
        // 依据: Category accordion: score bar + item list with severity colors (critical/high/medium/low)
        "按类别折叠展示：各类评分条 + 条目列表（critical/high/medium/low 颜色）",
      ],
      actions: [
        "查看整体合规评分了解当前等保达标状态。",
        "展开各类别查看具体失败项与严重程度。",
        "优先处理 critical 级别失败项以提升合规评分。",
      ],
      related: [
        { label: "数据治理", href: "/admin/governance" },
        { label: "凭证管理", href: "/admin/credentials" },
        { label: "权限管理", href: "/admin/permissions" },
      ],
    },
  },

  {
    match: "/admin/credentials",
    key: "/admin/credentials",
    guide: {
      title: "凭证管理",
      summary: "生成与轮换系统 API 凭证，查看操作审计。",
      features: [
        // 依据: admin/credentials/page.tsx L164, GET /api/admin/security/keys (list), /audit
        "凭证列表（GET /api/admin/security/keys）与审计日志（GET /api/admin/security/audit）",
        // 依据: POST /api/admin/security/keys/generate (name → new key)
        "生成新凭证（POST /api/admin/security/keys/generate）",
        // 依据: POST /api/admin/security/keys/[name]/rotate
        "轮换凭证（POST /api/admin/security/keys/[name]/rotate）",
        // 依据: Key names shown, values hidden (••••••••••••)
        "凭证值脱敏展示（值以 •••• 隐藏）",
        // 依据: Audit log: ts/action/key/actor
        "操作审计：时间 / 操作类型 / 凭证名 / 操作人",
      ],
      actions: [
        "填写凭证名称后点击「生成」创建新凭证，立即复制保存。",
        "对已有凭证点击「轮换」生成新值并废弃旧值。",
        "在审计日志标签页查看凭证操作历史。",
      ],
      related: [
        { label: "等保合规", href: "/admin/compliance" },
        { label: "开发者 API", href: "/developers" },
      ],
    },
  },

  {
    match: "/admin/integrations",
    key: "/admin/integrations",
    guide: {
      title: "系统集成",
      summary: "管理与外部系统（PLM/MES/ERP）的集成配置。",
      features: [
        // 依据: admin/integrations/page.tsx L157, Types: plm/mes/erp/custom; Auth: api_key/oauth2/basic/jwt
        "集成类型：PLM / MES / ERP / 自定义；认证方式：API Key / OAuth2 / Basic / JWT",
        // 依据: STATUS_COLOR: active/inactive/error
        "集成状态标注：活跃 / 非活跃 / 错误（颜色区分）",
        "集成配置 CRUD（创建 / 查看 / 编辑 / 删除）",
      ],
      actions: [
        "点击「新增集成」选择类型和认证方式后填写连接信息。",
        "查看状态颜色快速识别异常集成并排查。",
        "点击编辑图标修改已有集成的配置参数。",
      ],
      related: [
        { label: "Webhook 管理", href: "/admin/webhooks" },
        { label: "凭证管理", href: "/admin/credentials" },
      ],
    },
  },

  {
    match: "/admin/webhooks",
    key: "/admin/webhooks",
    guide: {
      title: "Webhook 管理",
      summary: "配置事件推送 Webhook，支持测试与开关。",
      features: [
        // 依据: admin/webhooks/page.tsx, GET/POST/DELETE /api/admin/webhooks
        "Webhook 列表 CRUD（GET/POST/DELETE /api/admin/webhooks）",
        // 依据: POST /api/admin/webhooks/[id]/test
        "测试 Webhook（POST /api/admin/webhooks/[id]/test）",
        // 依据: PUT /api/admin/webhooks/[id] for toggle
        "启用/停用 Webhook（PUT /api/admin/webhooks/[id]）",
        // 依据: Event type toggle buttons
        "按事件类型订阅（切换按钮选择触发条件）",
      ],
      actions: [
        "点击「新建」填写目标 URL 和订阅的事件类型。",
        "点击「测试」发送测试请求验证 Webhook 连通性。",
        "点击开关临时停用或重新启用某条 Webhook。",
      ],
      related: [
        { label: "系统集成", href: "/admin/integrations" },
        { label: "系统日志", href: "/admin/logs" },
      ],
    },
  },

  {
    match: "/admin/permissions",
    key: "/admin/permissions",
    guide: {
      title: "权限管理",
      summary: "通过 RBAC 管理角色定义与用户角色分配。",
      features: [
        // 依据: admin/permissions/page.tsx, 2 tabs: roles/users
        "2 个标签页：角色管理 / 用户权限",
        // 依据: GET /api/admin/rbac/roles, /api/admin/rbac/users
        "角色列表（GET /api/admin/rbac/roles）与用户列表（GET /api/admin/rbac/users）",
        // 依据: POST /api/admin/rbac/users/[id]/roles (assign)
        "为用户分配角色（POST /api/admin/rbac/users/[id]/roles）",
        // 依据: DELETE /api/admin/rbac/users/[id]/roles/[roleName] (revoke)
        "撤销用户角色（DELETE /api/admin/rbac/users/[id]/roles/[roleName]）",
      ],
      actions: [
        "在「角色」标签页查看所有角色及其权限定义。",
        "切换至「用户权限」标签页选择用户并分配角色。",
        "点击已有角色标签旁的「✕」撤销该角色分配。",
      ],
      related: [
        { label: "个人设置（管理员）", href: "/settings" },
        { label: "等保合规", href: "/admin/compliance" },
        { label: "审计日志", href: "/admin/audit" },
      ],
    },
  },

  {
    match: "/admin/billing",
    key: "/admin/billing",
    guide: {
      title: "计费管理",
      summary: "查看账单记录与订阅套餐，支持在线支付。",
      features: [
        // 依据: admin/billing/page.tsx, 2 tabs: bills/plans
        "2 个标签页：账单记录 / 订阅套餐",
        // 依据: GET /api/admin/billing/bills and /plans
        "账单列表（GET /api/admin/billing/bills）与套餐列表（GET /api/admin/billing/plans）",
        // 依据: POST /api/admin/billing/bills/[id]/pay
        "在线支付账单（POST /api/admin/billing/bills/[id]/pay）",
      ],
      actions: [
        "在「账单」标签页查看历史账单明细。",
        "点击账单旁的「支付」按钮完成在线结算。",
        "切换至「套餐」标签页了解或升级订阅方案。",
      ],
      related: [
        { label: "配额管理", href: "/admin/quota" },
        { label: "平台总览", href: "/platform/dashboard" },
      ],
    },
  },

  {
    match: "/admin/quota",
    key: "/admin/quota",
    guide: {
      title: "配额使用情况",
      summary: "查看查询、Token、存储等资源配额用量。",
      features: [
        // 依据: admin/quota/page.tsx delegates to QuotaPanel component
        // QuotaPanel: GET /api/admin/quota, UsageSummary: queries/tokens/storage_mb/users/documents/features
        "配额面板（QuotaPanel 组件，GET /api/admin/quota）",
        "5 项配额进度条：查询次数 / LLM Tokens / 存储(MB) / 用户数 / 文档数",
        // 依据: QuotaPanel L18, color: red>=90%, yellow>=70%, blue otherwise
        "进度条颜色预警：红色(≥90%) / 黄色(≥70%) / 蓝色(正常)",
        // 依据: features: Record<string, boolean>
        "功能开关状态展示（已启用/未启用）",
      ],
      actions: [
        "查看各配额项的已用量与上限。",
        "关注红色和黄色进度条，及时联系扩容。",
        "查看功能开关状态确认当前订阅包含的能力。",
      ],
      related: [
        { label: "计费管理", href: "/admin/billing" },
        { label: "LLM 用量", href: "/admin/usage" },
      ],
    },
  },

  {
    match: "/admin/tenant-settings",
    key: "/admin/tenant-settings",
    guide: {
      title: "租户设置",
      summary: "查看与修改当前租户的全局配置参数。",
      features: [
        // 依据: admin/tenant-settings/page.tsx, GET /api/admin/tenant-settings, PUT /api/admin/tenant-settings
        "租户配置读取（GET /api/admin/tenant-settings）与保存（PUT）",
        "设置表单与保存按钮",
      ],
      actions: [
        "查看当前租户的全局配置项。",
        "修改配置项后点击「保存」使设置生效。",
      ],
      related: [
        { label: "配额管理", href: "/admin/quota" },
        { label: "权限管理", href: "/admin/permissions" },
      ],
    },
  },

  {
    match: "/admin/feedback",
    key: "/admin/feedback",
    guide: {
      title: "反馈分析",
      summary: "分析用户反馈，定位答案错误与问题块。",
      features: [
        // 依据: admin/feedback/page.tsx, 3 tabs: overview/errors/chunks
        "3 个标签页：概览 / 错误案例 / 问题块",
        // 依据: GET /api/admin/feedback/overview-stats, /error-cases, /problematic-chunks
        "各标签 API：概览统计 / 错误案例 / 问题知识块",
        // 依据: POST /api/admin/feedback/resolve
        "标记错误案例为已解决（POST /api/admin/feedback/resolve）",
      ],
      actions: [
        "在「概览」标签查看反馈总体指标。",
        "切换至「错误案例」标签查看用户标记的错误答案。",
        "点击「解决」标记已修复的错误案例。",
        "切换至「问题块」标签识别需要重新处理的知识块。",
      ],
      related: [
        { label: "数据质量", href: "/admin/data-quality" },
        { label: "评测中心", href: "/admin/eval" },
      ],
    },
  },

  {
    match: "/admin/reports",
    key: "/admin/reports",
    guide: {
      title: "报表管理",
      summary: "管理自动化报表任务的创建、运行与导出。",
      features: [
        // 依据: admin/reports/page.tsx, GET /api/admin/reports
        "报表列表（GET /api/admin/reports）",
        // 依据: POST /api/admin/reports/[id]/run, /export?fmt=pdf
        "触发运行（POST /[id]/run）与 PDF 导出（POST /[id]/export?fmt=pdf）",
        // 依据: DELETE /api/admin/reports/[id]
        "删除报表（DELETE /[id]）",
        // 依据: Link to /admin/reports/new, /admin/reports/[id]/edit
        "跳转至新建或编辑报表页面",
      ],
      actions: [
        "点击「新建报表」跳转至创建页配置报表内容。",
        "点击「运行」立即生成最新报表数据。",
        "点击「导出 PDF」下载报表文件。",
        "点击编辑图标修改报表配置。",
      ],
      related: [
        { label: "用户行为统计", href: "/admin/analytics" },
        { label: "LLM 用量", href: "/admin/usage" },
      ],
    },
  },

  {
    match: "/admin/reports/new",
    key: "/admin/reports/new",
    guide: {
      title: "新建报表",
      summary: "填写表单创建新的自动化报表任务。",
      features: [
        // 依据: admin/reports/new/page.tsx, POST /api/admin/reports (create report)
        "报表创建（POST /api/admin/reports）",
        // 依据: Back button
        "返回报表列表按钮",
      ],
      actions: [
        "填写报表名称、数据源和调度配置后点击「创建」。",
        "点击「返回」取消并回到报表列表。",
      ],
      related: [{ label: "报表管理", href: "/admin/reports" }],
    },
  },
];
