import type { GuideEntry } from "./types";

export const contentGuides: GuideEntry[] = [
  {
    match: "/references",
    key: "/references",
    guide: {
      title: "引用关系图",
      summary: "可视化文档间引用与被引用关系网络。",
      features: [
        // 依据: references/page.tsx, ReferenceGraph + ReferenceDetailPanel components
        "引用图可视化（ReferenceGraph 组件）与详情面板（ReferenceDetailPanel）",
        // 依据: search, focus by doc_id, depth selector (1-2 hops)
        "文档搜索、按 doc_id 聚焦与跳转深度选择（1-2 跳）",
        // 依据: showImplicit checkbox toggle
        "隐式边开关（showImplicit 复选框）",
        // 依据: stats, legend, Reset view button
        "统计面板、图例与重置视图按钮",
      ],
      actions: [
        "在搜索框输入 doc_id 聚焦某文档，选择跳转深度（1 或 2 跳）。",
        "勾选「显示隐式边」展示推断的引用关系。",
        "点击节点在右侧详情面板查看引用来源与去向。",
        "点击「重置视图」恢复默认视角。",
      ],
      related: [
        { label: "知识图谱", href: "/graph" },
        { label: "文档库", href: "/library" },
      ],
    },
  },

  {
    match: "/favorites",
    key: "/favorites",
    guide: {
      title: "收藏夹",
      summary: "管理收藏的章节、文档与问答记录。",
      features: [
        // 依据: favorites/page.tsx, 4 tabs: all/section/document/query
        "4 个标签页：全部 / 章节 / 文档 / 问答",
        // 依据: useFavorites hook with addFavorite/removeFavorite/onPatchNote
        "收藏管理：添加、删除与内联笔记编辑（useFavorites hook）",
        // 依据: FavoriteCard, Edit3 icon, save/cancel inline edit
        "FavoriteCard 内联笔记编辑（Edit3 图标，保存/取消）",
        // 依据: Link to /query?q= for query favorites, /library/[doc_id] for section/document
        "问答收藏跳转至 /query?q=，章节/文档跳转至 /library/[doc_id]",
      ],
      actions: [
        "切换标签页筛选收藏类型。",
        "点击 Edit3 图标为收藏项添加或修改笔记。",
        "点击收藏卡片标题跳转至原始内容页面。",
        "点击删除图标取消收藏。",
      ],
      related: [
        { label: "知识问答", href: "/query" },
        { label: "文档库", href: "/library" },
        { label: "我的笔记", href: "/notes" },
      ],
    },
  },

  {
    match: "/notes",
    key: "/notes",
    guide: {
      title: "我的笔记",
      summary: "创建、搜索与管理带标签的个人笔记。",
      features: [
        // 依据: notes/page.tsx, GET/POST/PUT/DELETE /api/notes
        "笔记 CRUD（GET/POST/PUT/DELETE /api/notes）",
        // 依据: search via ?q= query param
        "关键词搜索（?q= 参数）",
        // 依据: Tags: comma/space/Chinese comma split
        "标签系统（逗号 / 空格 / 中文逗号分隔）",
        // 依据: Export note functionality
        "单条笔记导出功能",
      ],
      actions: [
        "点击「新建笔记」填写内容和标签，点击保存。",
        "在搜索框输入关键词过滤笔记列表。",
        "点击笔记卡片进入编辑模式，修改后保存。",
        "点击导出按钮下载单条笔记。",
      ],
      related: [
        { label: "收藏夹", href: "/favorites" },
        { label: "知识问答", href: "/query" },
      ],
    },
  },

  {
    match: "/compare",
    key: "/compare",
    guide: {
      title: "文档对比",
      summary: "并排比较两份文档的内容差异与图谱变化。",
      features: [
        // 依据: compare/page.tsx, DocSelector picks two documents
        "双文档选择器（DocSelector 组件）",
        // 依据: GET /api/documents/[id] for each side
        "分别加载两份文档内容（GET /api/documents/[id]）",
        // 依据: POST /api/compare/documents for graph changes (GraphDiffPanel)
        "知识图谱差异面板（POST /api/compare/documents，GraphDiffPanel）",
        // 依据: Word diff rendering, diff summary: added/removed/modified sections
        "逐词差异渲染与 Diff 摘要（新增/删除/修改章节数）",
        // 依据: showWordDiff toggle, search highlight, export
        "逐词对比开关、关键词高亮与导出功能",
      ],
      actions: [
        "分别从左右选择器选择要对比的两份文档。",
        "查看 Diff 摘要了解新增/删除/修改的章节数。",
        "开启「逐词对比」查看细粒度文字差异。",
        "点击导出下载对比报告。",
      ],
      related: [
        { label: "文档库", href: "/library" },
        { label: "版本时间轴", href: "/timeline" },
        { label: "知识图谱", href: "/graph" },
      ],
    },
  },

  {
    match: "/timeline",
    key: "/timeline",
    guide: {
      title: "版本时间轴",
      summary: "按日期浏览知识库文档入库历史。",
      features: [
        // 依据: timeline/page.tsx, GET /api/timeline → daily area chart
        "日期面积图（recharts AreaChart，GET /api/timeline）",
        // 依据: Click date bar → GET /api/timeline/docs?date= for docs that day
        "点击日期柱子加载当天入库文档列表（GET /api/timeline/docs?date=）",
        // 依据: Brush component for zooming
        "Brush 组件支持时间轴缩放",
        // 依据: TimelineCompare component for opening comparison
        "在时间轴上发起文档对比（TimelineCompare 组件）",
      ],
      actions: [
        "查看面积图了解知识库随时间增长趋势。",
        "点击某日期柱子，在下方查看当天入库的文档列表。",
        "拖拽 Brush 区间缩放查看特定时间段。",
        "选中两份文档后点击「对比」跳转至文档对比页。",
      ],
      related: [
        { label: "文档对比", href: "/compare" },
        { label: "文档库", href: "/library" },
      ],
    },
  },

  {
    match: "/wiki",
    key: "/wiki",
    guide: {
      title: "规范 Wiki",
      summary: "按规范类型分组浏览知识库规范索引。",
      features: [
        // 依据: wiki/page.tsx, GET /api/wiki/index
        "规范索引列表（GET /api/wiki/index）",
        // 依据: client-side filter by q, grouped by spec_type
        "客户端关键词过滤，按 spec_type 分组展示",
        // 依据: Grid of cards linking to /wiki/[doc_id]
        "卡片网格，点击跳转至规范详情 /wiki/[doc_id]",
      ],
      actions: [
        "在搜索框输入关键词过滤规范列表。",
        "点击规范卡片查看详情，包含摘要、范围与关键术语。",
      ],
      related: [
        { label: "文档库", href: "/library" },
        { label: "全局搜索", href: "/search" },
      ],
    },
  },

  {
    match: "/cypher",
    key: "/cypher",
    guide: {
      title: "Cypher 查询",
      summary: "图数据库查询工具，含管理员工作台。",
      features: [
        // 依据: cypher/page.tsx, URL param ?tab=builder|admin
        "两个标签页：builder（图谱构建器）/ admin（管理员工作台），通过 ?tab= 切换",
        // 依据: CypherBuilderWorkbench component
        "图谱构建器工作台（CypherBuilderWorkbench 组件）",
        // 依据: AdminCypherWorkbench (admin only)
        "管理员 Cypher 执行工作台（AdminCypherWorkbench，仅管理员可见）",
        // 依据: isAdmin check from useCurrentUser hook
        "权限控制：isAdmin 由 useCurrentUser hook 读取",
      ],
      actions: [
        "切换至 builder 标签页在图谱构建器中可视化构建查询。",
        "管理员切换至 admin 标签页执行原生 Cypher 语句。",
        "通过 URL 直接追加 ?tab=builder 或 ?tab=admin 切换视图。",
      ],
      related: [
        { label: "知识图谱", href: "/graph" },
        { label: "图谱 Schema", href: "/admin/schema" },
      ],
    },
  },

  {
    match: "/analytics",
    key: "/analytics",
    guide: {
      title: "使用分析",
      summary: "查询、质量、知识与运营四维度用量图表。",
      features: [
        // 依据: analytics/page.tsx, 4 tabs: 使用情况/答案质量/知识使用/运营指标
        "4 个标签页：使用情况 / 答案质量 / 知识使用 / 运营指标",
        // 依据: 4 period options: 7d/30d/90d/1y
        "时间范围选择：7天 / 30天 / 90天 / 1年",
        // 依据: Lazy load per tab: GET /api/analytics/{usage|quality|knowledge|operations}?period=
        "按需加载各标签数据（GET /api/analytics/{usage|quality|knowledge|operations}?period=）",
        // 依据: Refresh button reloads current tab
        "刷新按钮重新加载当前标签数据",
      ],
      actions: [
        "切换标签页查看不同维度的使用分析数据。",
        "选择时间范围过滤统计周期。",
        "点击刷新按钮获取最新数据。",
      ],
      related: [
        { label: "管理员统计分析", href: "/admin/analytics" },
        { label: "LLM 用量", href: "/admin/usage" },
      ],
    },
  },
];
