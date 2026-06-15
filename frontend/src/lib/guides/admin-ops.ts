import type { GuideEntry } from "./types";

export const adminOpsGuides: GuideEntry[] = [
  {
    match: "/admin/dashboard",
    key: "/admin/dashboard",
    guide: {
      title: "系统健康看板",
      summary: "系统综合健康状态，每 30 秒自动刷新。",
      features: [
        // 依据: admin/dashboard/page.tsx L?, useDashboard hook, 30s auto-refresh
        "30 秒自动刷新（useDashboard hook，subtitle 注明「每 30 秒自动刷新」）",
        // 依据: DashboardKPIs, DashboardCharts, DashboardActions
        "KPI 看板（DashboardKPIs）/ 图表区（DashboardCharts）/ 操作面板（DashboardActions）",
        // 依据: Manual refresh button, lastRefresh timestamp
        "手动刷新按钮与上次刷新时间戳",
      ],
      actions: [
        "查看 KPI 面板了解系统整体健康状态。",
        "点击手动刷新按钮立即更新数据。",
        "在操作面板中执行快捷运维操作。",
      ],
      related: [
        { label: "系统状态", href: "/admin/status" },
        { label: "系统指标", href: "/admin/metrics" },
        { label: "系统日志", href: "/admin/logs" },
      ],
    },
  },

  {
    match: "/admin/analytics",
    key: "/admin/analytics",
    guide: {
      title: "用户行为统计",
      summary: "分析用户活跃度、策略使用与缓存命中。",
      features: [
        // 依据: admin/analytics/page.tsx L?, 5 tabs: user/dept/dau/strategy/cache
        "5 个标签页：用户 / 部门 / DAU / 策略 / 缓存",
        // 依据: Day selector: 7/14/30/90 days
        "时间范围：7 / 14 / 30 / 90 天",
        // 依据: APIs: /api/admin/analytics/user-activity, strategy-stats, semantic-cache/stats
        "API：用户活动 / 策略统计 / 语义缓存命中（GET /api/admin/analytics/...）",
        // 依据: CSV export: /api/admin/analytics/user-activity/csv
        "用户活动 CSV 导出（GET /api/admin/analytics/user-activity/csv）",
        // 依据: UserTable, DeptTable, DauView, StrategyTab
        "各标签对应独立视图组件（UserTable / DeptTable / DauView / StrategyTab）",
      ],
      actions: [
        "切换标签页查看不同维度的用户行为数据。",
        "选择时间范围调整统计周期。",
        "在「用户」标签页点击导出按钮下载 CSV 报表。",
      ],
      related: [
        { label: "LLM 用量", href: "/admin/usage" },
        { label: "审计日志", href: "/admin/audit" },
        { label: "用量分析", href: "/analytics" },
      ],
    },
  },

  {
    match: "/admin/usage",
    key: "/admin/usage",
    guide: {
      title: "LLM 用量统计",
      summary: "查看各模型的 Token 消耗与成本明细。",
      features: [
        // 依据: admin/usage/page.tsx, GET /api/admin/usage
        "用量汇总（GET /api/admin/usage）",
        // 依据: LLM cost breakdown, model detail table
        "LLM 成本分解与各模型用量明细表",
        // 依据: UserUsageTable sub-component
        "用户级用量明细表（UserUsageTable 组件）",
      ],
      actions: [
        "查看各模型的 Token 消耗与成本占比。",
        "在用户明细表中查看各用户的用量分布。",
      ],
      related: [
        { label: "用户行为统计", href: "/admin/analytics" },
        { label: "配额管理", href: "/admin/quota" },
      ],
    },
  },

  {
    match: "/admin/metrics",
    key: "/admin/metrics",
    guide: {
      title: "系统指标",
      summary: "性能延迟、错误率与请求量三维度监控。",
      features: [
        // 依据: admin/metrics/page.tsx, 3 tabs: performance/errors/volume
        "3 个标签页：性能 / 错误 / 请求量",
        // 依据: APIs: /api/admin/metrics/performance, /errors, /volume (with ?days=)
        "各维度 API（GET /api/admin/metrics/{performance|errors|volume}?days=）",
        // 依据: Day selector for time range
        "时间范围选择器（天数）",
      ],
      actions: [
        "切换标签页查看性能延迟、错误率或请求量趋势。",
        "调整时间范围聚焦特定时段的指标变化。",
      ],
      related: [
        { label: "系统状态", href: "/admin/status" },
        { label: "系统日志", href: "/admin/logs" },
        { label: "实时监控", href: "/realtime" },
      ],
    },
  },

  {
    match: "/admin/logs",
    key: "/admin/logs",
    guide: {
      title: "系统日志",
      summary: "按服务和日志级别过滤查看系统日志。",
      features: [
        // 依据: admin/logs/page.tsx, GET /api/... with filter (line/level/service)
        "日志查询，支持 line / level / service 过滤参数",
        "多日志级别（INFO / WARNING / ERROR 等）",
      ],
      actions: [
        "选择服务和日志级别过滤日志列表。",
        "搜索关键词定位特定日志条目。",
      ],
      related: [
        { label: "系统指标", href: "/admin/metrics" },
        { label: "审计日志", href: "/admin/audit" },
        { label: "系统状态", href: "/admin/status" },
      ],
    },
  },

  {
    match: "/admin/audit",
    key: "/admin/audit",
    guide: {
      title: "审计日志",
      summary: "全局操作审计与图谱变更审计双视图。",
      features: [
        // 依据: admin/audit/page.tsx, 2 tabs: global (GET /api/admin/audit/events) and graph (GET /api/users/audit-logs)
        "2 个标签页：全局审计（GET /api/admin/audit/events）/ 图谱审计（GET /api/users/audit-logs）",
        // 依据: Event detail panel on click
        "点击事件行展开详情面板",
      ],
      actions: [
        "切换标签页查看全局操作或图谱变更记录。",
        "点击任意事件行查看详细操作信息。",
        "按时间范围或操作类型过滤日志。",
      ],
      related: [
        { label: "系统日志", href: "/admin/logs" },
        { label: "用户审计详情", href: "/admin/audit/users/[id]" },
      ],
    },
  },

  {
    match: "/admin/ops",
    key: "/admin/ops",
    guide: {
      title: "AI 工程台",
      summary: "管理评测 Harness 与基线配置的工程平台。",
      features: [
        // 依据: admin/ops/page.tsx, Title "AI 工程台", 2 workspace tabs: harness/baseline
        "2 个工作区标签：Harness / 基线（OpsHarnessTab / OpsBaselineTab）",
        // 依据: Overview table of recent runs
        "最近运行记录总览表",
      ],
      actions: [
        "切换至 Harness 标签页配置和运行评测 Harness。",
        "切换至基线标签页管理评测基准配置。",
        "在总览表中查看最近的运行结果。",
      ],
      related: [
        { label: "评测中心", href: "/admin/eval" },
        { label: "系统指标", href: "/admin/metrics" },
      ],
    },
  },

  {
    match: "/admin/status",
    key: "/admin/status",
    guide: {
      title: "系统状态",
      summary: "数据库、向量库等核心服务的实时健康状态。",
      features: [
        // 依据: admin/status/page.tsx, GET /api/admin/ops/overview
        "服务健康状态（GET /api/admin/ops/overview）",
        // 依据: Services: neo4j, milvus, elasticsearch (ServiceInfo: state/latency_ms)
        "核心服务监控：Neo4j / Milvus / Elasticsearch（状态 + 延迟 ms）",
        // 依据: Runtime stats: total/running/failed/queued/completed tasks
        "运行时任务统计：总数 / 运行中 / 失败 / 排队 / 完成",
        // 依据: Presence: active_users, requests_1m
        "在线状态：活跃用户数 / 最近 1 分钟请求量",
      ],
      actions: [
        "查看各服务状态指示灯和延迟数值。",
        "关注任务统计中的失败数，及时排查问题。",
        "查看在线用户数与实时请求量。",
      ],
      related: [
        { label: "系统健康看板", href: "/admin/dashboard" },
        { label: "系统指标", href: "/admin/metrics" },
        { label: "实时监控", href: "/realtime" },
      ],
    },
  },
];
