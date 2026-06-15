import type { GuideEntry } from "./types";

export const adminAiGuides: GuideEntry[] = [
  {
    match: "/admin/gnn",
    key: "/admin/gnn",
    guide: {
      title: "GNN 训练管理",
      summary: "管理图神经网络嵌入模型的训练与刷新。",
      features: [
        // 依据: admin/gnn/page.tsx L270, GET /api/gnn/status
        "训练状态查询（GET /api/gnn/status）：loaded / num_nodes / emb_dim",
        // 依据: POST /api/gnn/train, POST /api/gnn/refresh
        "启动训练（POST /api/gnn/train）与刷新嵌入（POST /api/gnn/refresh）",
        // 依据: TrainSt: running/error/progress; poll every 2s while training
        "训练进度实时轮询（2 秒间隔，state: running/error/progress）",
        // 依据: Advanced params: epochs, lr, batch_size, dropout, temperature, patience, device (cpu/cuda)
        "高级训练参数：epochs / lr / batch_size / dropout / temperature / patience / device (cpu|cuda)",
        // 依据: showHelp toggle
        "帮助面板开关（showHelp 切换）",
      ],
      actions: [
        "查看当前 GNN 服务状态（节点数与嵌入维度）。",
        "展开高级参数面板调整超参数后点击「开始训练」。",
        "训练完成后点击「刷新嵌入」更新向量索引。",
      ],
      related: [
        { label: "知识图谱", href: "/graph" },
        { label: "检索权重实验室", href: "/admin/lab" },
      ],
    },
  },

  {
    match: "/admin/finetune",
    key: "/admin/finetune",
    guide: {
      title: "模型微调",
      summary: "管理大语言模型微调任务的创建与部署。",
      features: [
        // 依据: admin/finetune/page.tsx L193, GET /api/admin/finetune (job list)
        "微调任务列表（GET /api/admin/finetune）",
        // 依据: POST /api/admin/finetune (create), POST /cancel, POST /deploy
        "创建任务（POST /api/admin/finetune）/ 取消 / 部署",
        // 依据: Status-based action buttons
        "按任务状态显示可用操作按钮",
      ],
      actions: [
        "点击「新建」配置微调数据集和超参数并提交。",
        "对运行中任务点击「取消」中止训练。",
        "训练完成后点击「部署」将模型上线使用。",
      ],
      related: [
        { label: "本地模型管理", href: "/admin/local-models" },
        { label: "评测中心", href: "/admin/eval" },
      ],
    },
  },

  {
    match: "/admin/local-models",
    key: "/admin/local-models",
    guide: {
      title: "本地模型管理",
      summary: "加载、卸载与基准测试本地部署的模型。",
      features: [
        // 依据: admin/local-models/page.tsx, GET /api/admin/local-models (models), /routes, /status
        "模型列表、路由配置与状态查询（GET /api/admin/local-models{/routes|/status}）",
        // 依据: POST /api/admin/local-models/[id]/load|unload|benchmark
        "模型加载 / 卸载 / 基准测试（POST /api/admin/local-models/[id]/{load|unload|benchmark}）",
        // 依据: POST /api/admin/local-models (create), DELETE /[id]
        "添加新模型（POST）与删除模型（DELETE /[id]）",
      ],
      actions: [
        "点击「加载」将指定模型加载至推理服务。",
        "点击「基准测试」评估模型吞吐量与延迟。",
        "点击「卸载」释放模型占用的 GPU 内存。",
        "点击「添加」录入新本地模型配置。",
      ],
      related: [
        { label: "模型微调", href: "/admin/finetune" },
        { label: "检索权重实验室", href: "/admin/lab" },
      ],
    },
  },

  {
    match: "/admin/prompts",
    key: "/admin/prompts",
    guide: {
      title: "提示词管理",
      summary: "管理系统内各场景使用的提示词模板。",
      features: [
        // 依据: admin/prompts/page.tsx delegates to PromptsAdminPanel
        "提示词管理面板（PromptsAdminPanel 组件）",
      ],
      actions: [
        "查看当前所有提示词模板列表。",
        "点击模板进入编辑模式，修改后保存生效。",
        "创建新模板用于自定义场景。",
      ],
      related: [
        { label: "检索权重实验室", href: "/admin/lab" },
        { label: "GNN 训练", href: "/admin/gnn" },
      ],
    },
  },

  {
    match: "/admin/lab",
    key: "/admin/lab",
    guide: {
      title: "检索权重实验室",
      summary: "实验并对比不同检索权重配置的效果。",
      features: [
        // 依据: admin/lab/page.tsx, Title "检索权重实验室"
        // GET/POST /api/admin/lab/history, POST /api/admin/lab/run-ab
        "实验历史记录（GET/POST /api/admin/lab/history）",
        "A/B 测试：同一问题用两套配置对比（POST /api/admin/lab/run-ab）",
        // 依据: Save/load/delete presets
        "预设配置保存、加载与删除",
        // 依据: graph_hops selector (1/2/3)
        "图跳转深度选择（1 / 2 / 3 跳）",
        // 依据: applyAsDefault button
        "「应用为默认配置」按钮",
      ],
      actions: [
        "配置两套检索参数，输入测试问题后点击「运行 A/B 测试」。",
        "对比两套配置的结果差异，选择更优方案。",
        "点击「应用为默认」将当前配置设为全局检索配置。",
        "保存实验配置为预设，方便后续复用。",
      ],
      related: [
        { label: "提示词管理", href: "/admin/prompts" },
        { label: "GNN 训练", href: "/admin/gnn" },
        { label: "评测中心", href: "/admin/eval" },
      ],
    },
  },

  {
    match: "/admin/ask-data",
    key: "/admin/ask-data",
    guide: {
      title: "数据问答",
      summary: "用自然语言查询数据并自动生成图表。",
      features: [
        // 依据: admin/ask-data/page.tsx, POST /api/analytics/nl-query
        "自然语言转查询（POST /api/analytics/nl-query）",
        // 依据: Example questions as quick buttons
        "示例问题快捷按钮",
        // 依据: Chart/table toggle view
        "图表 / 表格视图切换",
      ],
      actions: [
        "点击示例问题按钮快速体验数据问答。",
        "在输入框输入自然语言问题后点击查询。",
        "切换图表/表格视图选择最合适的展示方式。",
      ],
      related: [
        { label: "用户行为统计", href: "/admin/analytics" },
        { label: "LLM 用量", href: "/admin/usage" },
      ],
    },
  },

  {
    match: "/admin/cypher",
    key: "/admin/cypher",
    guide: {
      title: "管理员 Cypher",
      summary: "跳转至 Cypher 查询页的管理员标签。",
      features: [
        // 依据: admin/cypher/page.tsx redirect("/cypher?tab=admin")
        "服务端重定向至 /cypher?tab=admin",
      ],
      actions: ["访问此页将自动跳转至 /cypher?tab=admin。"],
      related: [{ label: "Cypher 查询", href: "/cypher" }],
    },
  },
];
