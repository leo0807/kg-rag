import type { GuideEntry } from "./types";

/**
 * 动态路由 guide 条目（全部使用 RegExp）。
 *
 * 必须置于 page-guides.ts 中所有 string 精确匹配项之后，
 * 以确保精确路由优先于正则路由。
 */
export const dynamicRouteGuides: GuideEntry[] = [
  // /library/[doc_id] — 单文档详情页
  {
    match: /^\/library\/[^/]+$/,
    key: "/library/[doc_id]",
    guide: {
      title: "文档详情",
      summary: "查看单份文档的章节结构与知识内容。",
      features: [
        "展示文档章节树与正文内容",
        "支持章节内容搜索与跳转",
        "关联实体、图谱节点快捷链接",
      ],
      actions: [
        "在章节列表中点击跳转至目标章节。",
        "点击实体名称跳转至知识图谱相关节点。",
        "返回文档库浏览更多文档。",
      ],
      related: [
        { label: "文档库", href: "/library" },
        { label: "全局搜索", href: "/search" },
        { label: "知识图谱", href: "/graph" },
      ],
    },
  },

  // /wiki/[doc_id] — Wiki 规范详情页
  {
    match: /^\/wiki\/[^/]+$/,
    key: "/wiki/[doc_id]",
    guide: {
      title: "规范详情",
      summary: "查看单份规范的摘要、范围与关键术语。",
      features: [
        // 依据: wiki/[doc_id]/page.tsx, GET /api/wiki/[doc_id]
        "规范内容加载（GET /api/wiki/[doc_id]）",
        // 依据: WikiCard: summary, scope, key_terms, related_specs, main_processes, involved_materials
        "展示字段：摘要 / 适用范围 / 关键术语 / 相关规范 / 主要流程 / 涉及材料",
      ],
      actions: [
        "查看规范摘要和适用范围快速了解文档定位。",
        "查看关键术语列表掌握领域专有名词。",
        "点击相关规范跳转至关联文档。",
      ],
      related: [
        { label: "规范 Wiki", href: "/wiki" },
        { label: "文档库", href: "/library" },
      ],
    },
  },

  // /generation/[task_id]/edit — 生成任务编辑页（三段，优先于二段详情）
  {
    match: /^\/generation\/[^/]+\/edit$/,
    key: "/generation/[task_id]/edit",
    guide: {
      title: "生成任务编辑",
      summary: "分章节编辑、再生成与定稿生成文档。",
      features: [
        // 依据: generation/[task_id]/edit/page.tsx, GET /api/generation/tasks/[id]
        "任务数据加载（GET /api/generation/tasks/[id]）",
        // 依据: SECTION_ORDER = ["1","2","3","4","6","7","8","9"]
        "章节侧边栏导航（SECTION_ORDER: 1/2/3/4/6/7/8/9）",
        // 依据: PUT /api/generation/tasks/[id]/section/[num]
        "章节保存（PUT /api/generation/tasks/[id]/section/[num]）",
        // 依据: POST /api/generation/tasks/[id]/regenerate/[num]
        "单章节重新生成（POST /[id]/regenerate/[num]）",
        // 依据: POST /api/generation/tasks/[id]/finalize
        "全文定稿（POST /[id]/finalize）与导出（ExportDialog）",
      ],
      actions: [
        "在左侧章节列表中点击切换编辑目标章节。",
        "编辑章节内容后点击保存，保留修改。",
        "对质量不满意的章节点击「重新生成」。",
        "所有章节通过验证后点击「定稿」导出文档。",
      ],
      related: [
        { label: "生成任务列表", href: "/generation" },
        { label: "新建生成任务", href: "/generation/new" },
      ],
    },
  },

  // /generation/[task_id] — 生成任务进度页（排除 new）
  {
    match: /^\/generation\/(?!new$)[^/]+$/,
    key: "/generation/[task_id]",
    guide: {
      title: "生成任务进度",
      summary: "实时监控文档生成任务的进度与章节预览。",
      features: [
        // 依据: generation/[task_id]/page.tsx, GET /api/generation/tasks/[id] + polling every 3s when running/pending
        "任务状态轮询（GET /api/generation/tasks/[id]，运行中/等待中时每 3 秒）",
        // 依据: ProgressPanel, SectionPreview sub-components
        "进度面板（ProgressPanel）与章节预览（SectionPreview）",
      ],
      actions: [
        "等待任务完成，进度面板实时更新各章节状态。",
        "任务完成后点击「前往编辑」进入编辑页精修内容。",
      ],
      related: [
        { label: "生成任务列表", href: "/generation" },
        { label: "生成任务编辑", href: "/generation/[task_id]/edit" },
      ],
    },
  },

  // /simulation/[id] — 仿真案例详情（排除静态子路由）
  {
    match: /^\/simulation\/(?!compare$|dashboard$|search$|workflows$)[^/]+$/,
    key: "/simulation/[id]",
    guide: {
      title: "仿真案例详情",
      summary: "查看单个仿真案例的输入参数、结果与云图。",
      features: [
        // 依据: simulation/[id]/page.tsx, GET /api/simulation/cases/[id], /results, /images
        "三路并行加载：案例信息 / 结果 / 图片（GET /api/simulation/cases/[id]{/results|/images}）",
        // 依据: 3 tabs: 输入参数 / 结果 / 云图
        "3 个标签页：输入参数 / 结果（max/min/avg + pass_status）/ 云图（图片网格）",
        // 依据: Related specs badges, confidence_level badge
        "相关规范徽章与可信度（confidence_level）标注",
      ],
      actions: [
        "在「输入参数」标签查看仿真配置与材料属性。",
        "切换至「结果」标签查看关键物理量的统计值与合格状态。",
        "切换至「云图」标签浏览仿真结果图像。",
      ],
      related: [
        { label: "仿真案例库", href: "/simulation" },
        { label: "仿真对比", href: "/simulation/compare" },
      ],
    },
  },

  // /platform/tenants/[id] — 租户详情（排除 new）
  {
    match: /^\/platform\/tenants\/(?!new$)[^/]+$/,
    key: "/platform/tenants/[id]",
    guide: {
      title: "租户详情",
      summary: "查看与管理单个租户的详细信息。",
      features: [
        // 依据: platform/tenants/[id]/page.tsx delegates to TenantDetail
        "租户详情视图（TenantDetail 组件）",
      ],
      actions: [
        "查看租户基本信息、用量统计与状态。",
        "点击「编辑」修改租户配置。",
        "点击「暂停」或「激活」切换租户状态。",
      ],
      related: [
        { label: "租户列表", href: "/platform/tenants" },
        { label: "平台总览", href: "/platform/dashboard" },
      ],
    },
  },

  // /admin/audit/users/[id] — 用户审计活动页
  {
    match: /^\/admin\/audit\/users\/[^/]+$/,
    key: "/admin/audit/users/[id]",
    guide: {
      title: "用户审计详情",
      summary: "查看单个用户的操作审计与行为统计。",
      features: [
        // 依据: admin/audit/users/[id]/page.tsx, GET /api/admin/audit/users/[id]/activity?limit=100
        "用户活动数据（GET /api/admin/audit/users/[id]/activity?limit=100）",
        // 依据: action_breakdown, resource_breakdown, recent events list
        "操作类型分布（action_breakdown）/ 资源分布（resource_breakdown）/ 最近事件列表",
        // 依据: ACTION_COLOR map: create/delete/update/read/auth
        "事件类型颜色标注：create / delete / update / read / auth",
      ],
      actions: [
        "查看该用户的操作类型分布图。",
        "在最近事件列表中查看具体操作记录。",
        "返回审计日志查看全局事件。",
      ],
      related: [
        { label: "审计日志", href: "/admin/audit" },
        { label: "权限管理", href: "/admin/permissions" },
      ],
    },
  },

  // /admin/eval/runs/[id] — 评测运行详情
  {
    match: /^\/admin\/eval\/runs\/[^/]+$/,
    key: "/admin/eval/runs/[id]",
    guide: {
      title: "评测运行详情",
      summary: "查看评测运行的摘要、错误分析与优化建议。",
      features: [
        // 依据: admin/eval/runs/[id]/page.tsx, GET /api/admin/eval/runs/[id]
        "运行数据加载（GET /api/admin/eval/runs/[id]）",
        // 依据: 3 tabs: summary/errors/suggestions
        "3 个标签页：摘要 / 错误案例 / 优化建议",
        // 依据: POST /api/admin/eval/runs/[id]/analyze (trigger analysis)
        "触发 AI 分析（POST /api/admin/eval/runs/[id]/analyze）",
        "生成报告按钮",
      ],
      actions: [
        "在「摘要」标签查看整体准确率与延迟指标。",
        "切换至「错误案例」标签查看具体失败问题。",
        "切换至「优化建议」标签查看改进方向。",
        "点击「触发分析」让 AI 深度分析错误模式。",
      ],
      related: [
        { label: "评测中心", href: "/admin/eval" },
        { label: "评测对比", href: "/admin/eval/compare" },
        { label: "评测趋势", href: "/admin/eval/trends" },
      ],
    },
  },

  // /shared/[token] — 分享会话只读视图
  {
    match: /^\/shared\/[^/]+$/,
    key: "/shared/[token]",
    guide: {
      title: "分享的对话",
      summary: "以只读方式查看他人分享的知识问答记录。",
      features: [
        // 依据: shared/[token]/page.tsx, fetch (not fetchApi) ${getApiBaseUrl()}/api/shared/[token]
        "无需认证加载分享内容（fetch /api/shared/[token]，不含 Authorization）",
        // 依据: Shows: title, messages array, created_at, view_count, expires_at
        "展示：标题 / 消息列表 / 创建时间 / 浏览次数 / 过期时间",
        // 依据: Read-only: Eye/MessageSquare icons
        "只读模式，使用 Eye / MessageSquare 图标标注",
      ],
      actions: [
        "浏览分享的对话消息，了解问答内容。",
        "查看链接过期时间，分享链接有效期有限。",
      ],
      related: [
        { label: "知识问答", href: "/query" },
      ],
    },
  },
];
