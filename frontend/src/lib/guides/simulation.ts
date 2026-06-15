import type { GuideEntry } from "./types";

export const simulationGuides: GuideEntry[] = [
  {
    match: "/simulation",
    key: "/simulation",
    guide: {
      title: "仿真案例库",
      summary: "按领域浏览与筛选仿真计算案例。",
      features: [
        // 依据: simulation/page.tsx, GET /api/simulation/cases?domain=&q=&limit=50
        "案例列表（GET /api/simulation/cases?domain=&q=&limit=50）",
        // 依据: Domain filter: structural/thermal/fluid/coupled
        "领域过滤：结构 / 热 / 流体 / 耦合（domain 参数）",
        // 依据: Confidence level badges: 已验证/参考/初步 (color-coded)
        "可信度徽章：已验证 / 参考 / 初步（不同颜色区分）",
      ],
      actions: [
        "选择领域过滤器缩小案例范围。",
        "在搜索框输入关键词查找特定仿真案例。",
        "点击案例卡片跳转至案例详情页。",
      ],
      related: [
        { label: "仿真仪表盘", href: "/simulation/dashboard" },
        { label: "仿真高级搜索", href: "/simulation/search" },
        { label: "仿真对比", href: "/simulation/compare" },
      ],
    },
  },

  {
    match: "/simulation/compare",
    key: "/simulation/compare",
    guide: {
      title: "仿真对比",
      summary: "并排比较 2-4 个仿真案例的结果与参数。",
      features: [
        // 依据: simulation/compare/page.tsx L?, Input 2-4 case IDs, POST /api/simulation/compare
        "输入 2-4 个案例 ID，发起对比（POST /api/simulation/compare）",
        // 依据: recharts BarChart with aligned result_name axis
        "结果柱状图对比（recharts BarChart，result_name 轴对齐）",
        // 依据: Input param comparison table (union of all params)
        "参数对比表（所有案例参数的并集）",
        // 依据: COLORS = ["#3B82F6","#F59E0B","#10B981","#8B5CF6"]
        "4 种颜色区分不同案例（蓝/黄/绿/紫）",
      ],
      actions: [
        "输入 2 至 4 个案例 ID，点击「对比」发起分析。",
        "查看柱状图对比各案例关键结果指标。",
        "查看参数对比表了解各案例的输入差异。",
      ],
      related: [
        { label: "仿真案例库", href: "/simulation" },
        { label: "仿真仪表盘", href: "/simulation/dashboard" },
      ],
    },
  },

  {
    match: "/simulation/dashboard",
    key: "/simulation/dashboard",
    guide: {
      title: "仿真仪表盘",
      summary: "仿真案例总览：KPI、分布图与快捷导航。",
      features: [
        // 依据: simulation/dashboard/page.tsx L?, GET /api/simulation/stats
        "汇总统计（GET /api/simulation/stats）",
        // 依据: KPIs: total, pending_review, running_workflows, rules_applied
        "关键指标：总案例数 / 待审核 / 运行中工作流 / 已应用规则",
        // 依据: 4 NAV cards to: /simulation, /simulation/search, /simulation/compare, /simulation/workflows
        "4 个快捷导航卡片（案例库 / 高级搜索 / 对比 / 工作流）",
        // 依据: Pie chart (domain_dist), recent cases list, pass_rate bar
        "领域分布饼图、最近案例列表与通过率进度条",
      ],
      actions: [
        "查看 KPI 卡片了解仿真任务总体状态。",
        "点击导航卡片快速跳转至各功能模块。",
        "查看饼图了解各领域案例分布比例。",
      ],
      related: [
        { label: "仿真案例库", href: "/simulation" },
        { label: "仿真工作流", href: "/simulation/workflows" },
        { label: "仿真对比", href: "/simulation/compare" },
      ],
    },
  },

  {
    match: "/simulation/search",
    key: "/simulation/search",
    guide: {
      title: "仿真高级搜索",
      summary: "按多维度参数精确筛选仿真案例。",
      features: [
        // 依据: simulation/search/page.tsx L?, POST /api/simulation/search with multiple params
        "多参数搜索（POST /api/simulation/search）",
        // 依据: domain, application, software, material, load_type, conf, temperature_range, pressure_range
        "支持条件：领域 / 应用场景 / 软件 / 材料 / 载荷类型 / 可信度 / 温度范围 / 压力范围",
        // 依据: Confidence filter: 已验证/参考/初步
        "可信度过滤：已验证 / 参考 / 初步",
      ],
      actions: [
        "填写所需的搜索条件（可只填部分字段）。",
        "选择可信度等级过滤结果质量。",
        "点击搜索查看符合条件的案例列表，点击跳转至详情。",
      ],
      related: [
        { label: "仿真案例库", href: "/simulation" },
        { label: "仿真仪表盘", href: "/simulation/dashboard" },
      ],
    },
  },

  {
    match: "/simulation/workflows",
    key: "/simulation/workflows",
    guide: {
      title: "仿真工作流",
      summary: "管理 DOE 试验设计工作流的创建与执行。",
      features: [
        // 依据: simulation/workflows/page.tsx L?, GET /api/simulation/workflows, POST to create
        "工作流列表与创建（GET /api/simulation/workflows，POST 新建）",
        // 依据: DOE types: full_factorial/latin_hypercube/sobol/adaptive (CN labels)
        "DOE 类型：全因子 / 拉丁超立方 / Sobol 序列 / 自适应",
        // 依据: Submit targets: local/slurm/pbs
        "提交目标：本地 / Slurm / PBS 集群",
        // 依据: Status actions: submit (draft), monitor (running), collect (completed)
        "状态操作：提交（草稿）/ 监控（运行中）/ 收集（已完成）",
        // 依据: Progress bar per workflow
        "每个工作流显示进度条",
      ],
      actions: [
        "点击「新建工作流」选择 DOE 类型和提交目标。",
        "对草稿状态工作流点击「提交」发送至计算集群。",
        "对运行中工作流点击「监控」查看实时进度。",
        "计算完成后点击「收集」汇总结果数据。",
      ],
      related: [
        { label: "仿真仪表盘", href: "/simulation/dashboard" },
        { label: "仿真案例库", href: "/simulation" },
      ],
    },
  },
];
