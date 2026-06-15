import type { GuideEntry } from "./types";

export const adminEvalGuides: GuideEntry[] = [
  {
    match: "/admin/eval",
    key: "/admin/eval",
    guide: {
      title: "评测中心",
      summary: "查看持久化评测运行记录与经典评测结果。",
      features: [
        // 依据: admin/eval/page.tsx L166, 2 tabs: "持久化评测"(runs) and "经典评测"(LegacyEvalPanel), L26, L73
        "2 个标签页：持久化评测（运行列表）/ 经典评测（LegacyEvalPanel）",
        // 依据: GET /api/admin/eval/runs, L33
        "运行列表（GET /api/admin/eval/runs）",
        // 依据: Table: run_name, status (color-coded), accuracy %, avg_latency_ms, completed/total, tags
        "运行表格：名称 / 状态（颜色标注）/ 准确率 / 平均延迟 / 完成进度 / 标签",
        // 依据: Link to /admin/eval/runs/[id], L120/L150
        "点击运行跳转至详情页 /admin/eval/runs/[id]",
        // 依据: Header quick-nav links: /admin/eval/datasets, /compare, /trends
        "顶部快捷导航：数据集 / 对比 / 趋势",
      ],
      actions: [
        "在持久化评测标签页查看所有评测运行记录。",
        "点击运行行跳转至 /admin/eval/runs/[id] 查看详情。",
        "切换至经典评测标签页查看历史基线结果。",
        "使用顶部导航快速跳转至数据集、对比或趋势页面。",
      ],
      related: [
        { label: "评测数据集", href: "/admin/eval/datasets" },
        { label: "评测对比", href: "/admin/eval/compare" },
        { label: "评测趋势", href: "/admin/eval/trends" },
      ],
    },
  },

  {
    match: "/admin/eval/datasets",
    key: "/admin/eval/datasets",
    guide: {
      title: "评测数据集",
      summary: "上传与管理评测基准问答数据集。",
      features: [
        // 依据: admin/eval/datasets/page.tsx, GET /api/admin/eval/datasets
        "数据集列表（GET /api/admin/eval/datasets）",
        // 依据: File upload with POST (multipart), DELETE /api/admin/eval/datasets/[id]
        "文件上传（POST multipart）与删除（DELETE /[id]）",
        // 依据: Toggle form show/hide
        "上传表单展开/收起切换",
      ],
      actions: [
        "点击「上传数据集」展开表单，选择文件后提交。",
        "在数据集列表中查看已有数据集的问答对数量。",
        "点击删除图标移除不再需要的数据集。",
      ],
      related: [
        { label: "评测中心", href: "/admin/eval" },
        { label: "评测对比", href: "/admin/eval/compare" },
      ],
    },
  },

  {
    match: "/admin/eval/compare",
    key: "/admin/eval/compare",
    guide: {
      title: "评测对比",
      summary: "选择两次评测运行进行准确率与延迟对比。",
      features: [
        // 依据: admin/eval/compare/page.tsx, GET /api/admin/eval/runs (for run selector)
        "运行选择器（GET /api/admin/eval/runs 获取可选列表）",
        // 依据: POST /api/admin/eval/runs/compare with {baseline_id, target_id}
        "发起对比分析（POST /api/admin/eval/runs/compare，{baseline_id, target_id}）",
        // 依据: Side-by-side accuracy/latency comparison
        "准确率与延迟并排对比展示",
      ],
      actions: [
        "分别从基线和目标下拉框选择两次评测运行。",
        "点击「对比」发起分析并查看结果差异。",
        "对比准确率提升与延迟变化，评估新版本效果。",
      ],
      related: [
        { label: "评测中心", href: "/admin/eval" },
        { label: "评测趋势", href: "/admin/eval/trends" },
      ],
    },
  },

  {
    match: "/admin/eval/trends",
    key: "/admin/eval/trends",
    guide: {
      title: "评测趋势",
      summary: "按时间轴展示评测准确率历史趋势。",
      features: [
        // 依据: admin/eval/trends/page.tsx, GET /api/admin/eval/runs
        "历史运行数据（GET /api/admin/eval/runs）",
        // 依据: Area/line chart of accuracy over time
        "准确率随时间变化的面积/折线图",
        // 依据: Historical runs table
        "历史运行列表（含准确率、延迟等指标）",
      ],
      actions: [
        "查看折线图了解准确率随版本迭代的变化趋势。",
        "在下方历史表格中定位特定运行的详细指标。",
        "点击运行行跳转至详情页查看具体问题的答案质量。",
      ],
      related: [
        { label: "评测中心", href: "/admin/eval" },
        { label: "评测对比", href: "/admin/eval/compare" },
      ],
    },
  },
];
