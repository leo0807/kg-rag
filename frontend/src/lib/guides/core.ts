import type { GuideEntry } from "./types";

export const coreGuides: GuideEntry[] = [
  {
    match: "/",
    key: "/",
    guide: {
      title: "首页",
      summary: "自动跳转至文档库入口。",
      features: [
        // 依据: app/page.tsx redirect("/ingest"); app/ingest/page.tsx useRouter().replace("/library")
        "服务端跳转 /ingest，/ingest 再客户端跳转 /library",
      ],
      actions: ["访问首页会自动跳转至文档库，无需手动操作。"],
      related: [
        { label: "文档库", href: "/library" },
        { label: "知识问答", href: "/query" },
      ],
    },
  },

  {
    match: "/query",
    key: "/query",
    guide: {
      title: "知识问答",
      summary: "多策略 GraphRAG 知识库对话系统。",
      features: [
        // 依据: StrategySelector L6-18, query/page.tsx
        "7 种检索策略：parallel / sequential / graph_augmented / multimodal / multi_hop / agent / counterfactual",
        // 依据: CompareMode toggle, InputBar L61-70，title "四策略对比模式"
        "四策略并排对比模式（GitCompare 图标，InputBar L61-70）",
        // 依据: HyDE toggle, pendingImages, query/page.tsx L40-60
        "HyDE 假设文档增强开关与图片上传（多模态检索）",
        // 依据: Export button, Download icon, InputBar L72-79
        "对话导出（Download 图标，InputBar L72-79）",
        // 依据: draft auto-save localStorage key "query:draft"
        "草稿自动保存至 localStorage（key: query:draft）",
      ],
      actions: [
        "在输入框输入问题，点击发送或按 Enter 获取答案。",
        "点击策略选择器切换检索策略；点击 GitCompare 图标启用对比模式。",
        "开启 HyDE 或上传图片进行多模态增强检索。",
        "点击 Download 图标导出当前对话记录。",
      ],
      related: [
        { label: "全局搜索", href: "/search" },
        { label: "知识图谱", href: "/graph" },
        { label: "收藏夹", href: "/favorites" },
      ],
    },
  },

  {
    match: "/search",
    key: "/search",
    guide: {
      title: "全局搜索",
      summary: "跨文档全文检索，支持实体关系展示。",
      features: [
        // 依据: search/page.tsx L40, debounce 300ms, GET /api/search/suggest?q=&limit=5
        "实时输入建议（GET /api/search/suggest，300ms 防抖）",
        // 依据: SuggestResult type, page.tsx L106-144: documents/sections/entities/suggested_questions
        "建议分组：文档 / 章节 / 相关实体 / 直接提问",
        // 依据: handleSearch L52, GET /api/search?q=&top_k=20
        "全文搜索返回章节列表（GET /api/search?q=&top_k=20）",
        // 依据: handleEntityClick L63-70, POST /api/admin/cypher/execute
        "点击实体展示关系统计（出现文档数 / 章节数）",
        // 依据: renderHighlight L73-75, r.highlight?.content?.[0] ?? r.snippet
        "关键词高亮渲染（highlight.content 优先于 snippet）",
      ],
      actions: [
        "在搜索框输入关键词，从下拉建议选择或按 Enter 执行搜索。",
        "点击建议中的实体名查看关系统计面板，再点击「搜索」。",
        "点击结果跳转至 /library/[doc_id] 文档详情页。",
        "点击关系面板中「查看图谱」跳转至知识图谱。",
      ],
      related: [
        { label: "高级搜索", href: "/advanced-search" },
        { label: "知识图谱", href: "/graph" },
        { label: "文档库", href: "/library" },
      ],
    },
  },

  {
    match: "/advanced-search",
    key: "/advanced-search",
    guide: {
      title: "高级搜索",
      summary: "约束检索、版本溯源与跨文档交叉引用。",
      features: [
        // 依据: advanced-search page constraints tab, GET /api/search/constraints
        "约束检索：按 type/unit/min_val/max_val/doc_id 过滤（GET /api/search/constraints）",
        // 依据: version tab, GET /api/graph/version-lineage/[doc_id]
        "版本溯源：查询文档版本血缘关系图（GET /api/graph/version-lineage/[doc_id]）",
        // 依据: cross-ref tab, GET /api/search/cross-references?target_doc=
        "交叉引用：查找引用同一目标文档的所有章节（GET /api/search/cross-references?target_doc=）",
      ],
      actions: [
        "切换「约束」标签页，填写参数类型和数值范围后搜索。",
        "切换「版本」标签页，输入文档 ID 查看版本血缘图。",
        "切换「交叉引用」标签页，输入目标文档 ID 查找所有引用源。",
      ],
      related: [
        { label: "全局搜索", href: "/search" },
        { label: "文档库", href: "/library" },
        { label: "引用关系图", href: "/references" },
      ],
    },
  },

  {
    match: "/library",
    key: "/library",
    guide: {
      title: "文档库",
      summary: "分页浏览、导入与重处理知识库文档。",
      features: [
        // 依据: library/page.tsx, GET /api/documents with pagination
        "分页文档列表（GET /api/documents，带分页参数）",
        // 依据: LibraryIngestTab, LibraryReprocessTab components
        "导入标签页（LibraryIngestTab）与重处理标签页（LibraryReprocessTab）",
        // 依据: ExportMenu component
        "导出菜单（ExportMenu 组件）",
        // 依据: BackfillProgressBar, ImageAnalysisBadge status indicators
        "积压进度条（BackfillProgressBar）与图片分析徽章（ImageAnalysisBadge）",
        // 依据: isAdmin check from localStorage
        "管理员功能按钮（isAdmin 从 localStorage 读取）",
      ],
      actions: [
        "浏览文档列表，点击文档名称跳转至详情页。",
        "切换至「导入」标签页上传新文档进入知识库。",
        "切换至「重处理」标签页对已有文档重新解析。",
        "点击导出菜单下载文档库内容。",
      ],
      related: [
        { label: "知识图谱", href: "/graph" },
        { label: "批量导入管理", href: "/admin/ingest" },
        { label: "全局搜索", href: "/search" },
      ],
    },
  },

  {
    match: "/graph",
    key: "/graph",
    guide: {
      title: "知识图谱",
      summary: "可视化探索文档知识节点与关系网络。",
      features: [
        // 依据: GraphToolbar, graph/page.tsx multiple render modes: SVG/Canvas/WebGL
        "多渲染模式：SVG / Canvas / WebGL（GraphToolbar 组件）",
        // 依据: useGraphPage hook, node/edge filters, search, doc filter, limits
        "节点/边过滤、全局搜索与文档范围过滤（useGraphPage hook）",
        // 依据: GraphWorkspace, zoom controls, export, share snapshot
        "缩放控制、图例、快照导出与分享（GraphWorkspace 组件）",
        // 依据: TourPanel component
        "引导游览面板（TourPanel 组件）",
      ],
      actions: [
        "使用工具栏切换渲染模式和过滤条件探索图谱。",
        "滚轮缩放或拖拽节点，点击节点查看详情。",
        "点击导出按钮保存图谱快照或分享链接。",
      ],
      related: [
        { label: "Cypher 查询", href: "/cypher" },
        { label: "引用关系图", href: "/references" },
        { label: "图谱 Schema", href: "/admin/schema" },
      ],
    },
  },

  {
    match: "/graph/builder",
    key: "/graph/builder",
    guide: {
      title: "图谱构建器",
      summary: "跳转至 Cypher 查询页图谱构建器标签。",
      features: [
        // 依据: graph/builder/page.tsx redirect("/cypher?tab=builder")
        "服务端重定向至 /cypher?tab=builder",
      ],
      actions: ["访问此页将自动跳转至 /cypher?tab=builder。"],
      related: [{ label: "Cypher 查询", href: "/cypher" }],
    },
  },

  {
    match: "/ingest",
    key: "/ingest",
    guide: {
      title: "文档导入",
      summary: "跳转至文档库页面。",
      features: [
        // 依据: ingest/page.tsx, useRouter().replace("/library")
        "客户端重定向至 /library（useRouter().replace）",
      ],
      actions: ["访问此页将自动跳转至文档库 /library。"],
      related: [{ label: "文档库", href: "/library" }],
    },
  },

  {
    match: "/pipeline",
    key: "/pipeline",
    guide: {
      title: "处理管道配置",
      summary: "可视化编辑与管理文档处理流水线。",
      features: [
        // 依据: pipeline/page.tsx, usePipeline hook: schema, configs, nodes, edges
        "多套配置管理：新建、删除、复制、设为默认（usePipeline hook）",
        // 依据: add/delete/connect nodes, nodes/edges state
        "画布式节点连线编辑（添加/删除节点、连接边）",
        // 依据: copy/paste/cut operations
        "复制/粘贴/剪切节点操作",
        // 依据: validate, save, clearCanvas
        "校验与保存配置，支持清空画布",
      ],
      actions: [
        "选择已有配置或点击「新建」创建管道。",
        "在画布上添加处理节点并用边连接。",
        "点击「校验」确认配置正确，再点击「保存」。",
        "点击「设为默认」将当前配置设为新文档的处理管道。",
      ],
      related: [
        { label: "文档库", href: "/library" },
        { label: "批量导入管理", href: "/admin/ingest" },
        { label: "任务处理队列", href: "/admin/processing" },
      ],
    },
  },

  {
    match: "/realtime",
    key: "/realtime",
    guide: {
      title: "实时监控",
      summary: "WebSocket 推送的查询流与性能看板。",
      features: [
        // 依据: realtime/page.tsx, wss://host/api/realtime/dashboard?token=..., auto-reconnect
        "WebSocket 实时连接（断线自动重连，wss://.../api/realtime/dashboard）",
        // 依据: ping every 25s
        "25 秒心跳 ping 保活",
        // 依据: LiveQueryFeed, LiveErrorMonitor, LivePerformanceMetrics
        "实时查询流（LiveQueryFeed）/ 错误监控（LiveErrorMonitor）/ 性能指标（LivePerformanceMetrics）",
        // 依据: Pause/resume toggle
        "暂停/恢复事件流切换按钮",
        // 依据: max 200 events in memory
        "内存中最多保留 200 条事件",
      ],
      actions: [
        "进入页面后 WebSocket 自动连接并开始推送事件。",
        "点击「暂停」按钮暂停事件流，再次点击继续。",
        "查看查询流、错误日志和性能指标三个子面板。",
      ],
      related: [
        { label: "系统指标", href: "/admin/metrics" },
        { label: "系统日志", href: "/admin/logs" },
        { label: "系统状态", href: "/admin/status" },
      ],
    },
  },
];
