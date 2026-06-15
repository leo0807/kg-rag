import type { GuideEntry } from "./types";

export const platformGuides: GuideEntry[] = [
  {
    match: "/platform/dashboard",
    key: "/platform/dashboard",
    guide: {
      title: "平台总览",
      summary: "多租户平台的整体运营状态看板。",
      features: [
        // 依据: platform/dashboard/page.tsx L?, GET /api/platform/dashboard
        "平台统计数据（GET /api/platform/dashboard）",
        // 依据: Stats: tenants (total/active/suspended/trial), total_users, queries_this_month
        "租户统计：总数 / 活跃 / 已暂停 / 试用；总用户数；本月查询量",
        // 依据: Expiring soon list (14 days)
        "即将到期租户列表（14 天内）",
        // 依据: Tenant status distribution bar chart
        "租户状态分布柱状图",
        // 依据: Quick actions: new tenant, manage list, view usage
        "快捷操作：新建租户 / 管理列表 / 查看用量",
      ],
      actions: [
        "查看 KPI 卡片了解平台整体租户与用量状态。",
        "关注「即将到期」列表，及时联系续约或处理。",
        "点击快捷操作跳转至相应管理页面。",
      ],
      related: [
        { label: "租户列表", href: "/platform/tenants" },
        { label: "用量统计", href: "/platform/usage" },
      ],
    },
  },

  {
    match: "/platform/tenants",
    key: "/platform/tenants",
    guide: {
      title: "租户列表",
      summary: "查看、搜索与管理所有平台租户。",
      features: [
        // 依据: platform/tenants/page.tsx delegates to TenantList component
        // TenantList: GET /api/platform/tenants, search filter, activate/suspend/delete
        "租户列表（GET /api/platform/tenants，TenantList 组件）",
        "关键词搜索过滤租户",
        "租户状态操作：激活 / 暂停 / 删除",
      ],
      actions: [
        "在搜索框输入租户名或 ID 过滤列表。",
        "点击「激活」或「暂停」切换租户状态。",
        "点击租户名跳转至租户详情页。",
        "点击「新建租户」进入创建表单。",
      ],
      related: [
        { label: "平台总览", href: "/platform/dashboard" },
        { label: "新建租户", href: "/platform/tenants/new" },
        { label: "用量统计", href: "/platform/usage" },
      ],
    },
  },

  {
    match: "/platform/tenants/new",
    key: "/platform/tenants/new",
    guide: {
      title: "新建租户",
      summary: "填写表单在平台上创建新的租户账户。",
      features: [
        // 依据: platform/tenants/new/page.tsx delegates to TenantForm
        "租户创建表单（TenantForm 组件）",
      ],
      actions: [
        "填写租户名称、联系信息和订阅套餐。",
        "点击「创建」提交表单，自动跳转至租户列表。",
        "点击「取消」返回租户列表不保存。",
      ],
      related: [
        { label: "租户列表", href: "/platform/tenants" },
        { label: "平台总览", href: "/platform/dashboard" },
      ],
    },
  },

  {
    match: "/platform/usage",
    key: "/platform/usage",
    guide: {
      title: "平台用量统计",
      summary: "查看各租户的资源使用情况图表。",
      features: [
        // 依据: platform/usage/page.tsx delegates to UsageChart component
        "用量图表（UsageChart 组件）",
      ],
      actions: [
        "查看各租户的查询量、Token 用量与存储占用图表。",
        "对比各租户资源消耗趋势。",
      ],
      related: [
        { label: "平台总览", href: "/platform/dashboard" },
        { label: "租户列表", href: "/platform/tenants" },
        { label: "LLM 用量", href: "/admin/usage" },
      ],
    },
  },
];
