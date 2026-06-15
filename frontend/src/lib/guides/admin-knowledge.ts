import type { GuideEntry } from "./types";

export const adminKnowledgeGuides: GuideEntry[] = [
  {
    match: "/admin/ingest",
    key: "/admin/ingest",
    guide: {
      title: "批量导入管理",
      summary: "管理批量文档导入任务的启停与进度监控。",
      features: [
        // 依据: admin/ingest/page.tsx L243, GET /api/admin/batch/status (poll every 2s)
        "实时轮询批量任务状态（GET /api/admin/batch/status，每 2 秒）",
        // 依据: POST /api/admin/batch/start|pause|resume|stop
        "批量任务控制：启动 / 暂停 / 恢复 / 停止（POST /api/admin/batch/{start|pause|resume|stop}）",
        // 依据: Directory input, progress grid (done/total/failed)
        "目录路径输入与进度网格（已完成 / 总数 / 失败数）",
        // 依据: real-time log panel (max 100 lines)
        "实时日志面板（最多 100 行）",
        // 依据: Log levels: INFO/ERROR/SUCCESS/WARNING (color-coded)
        "日志级别颜色标注：INFO / ERROR / SUCCESS / WARNING",
      ],
      actions: [
        "输入待导入目录路径，点击「启动」开始批量处理。",
        "任务运行中可点击「暂停」临时中断，再点击「恢复」继续。",
        "查看进度网格中的失败数，定位异常文件。",
        "在日志面板实时跟踪处理详情。",
      ],
      related: [
        { label: "文档库", href: "/library" },
        { label: "任务处理队列", href: "/admin/processing" },
        { label: "数据治理", href: "/admin/governance" },
      ],
    },
  },

  {
    match: "/admin/entities",
    key: "/admin/entities",
    guide: {
      title: "实体管理",
      summary: "搜索、浏览与合并知识图谱实体节点。",
      features: [
        // 依据: admin/entities/page.tsx L234, GET /api/entities?type=&q=&page=&per_page=50
        "分页实体列表（GET /api/entities?type=&q=&page=&per_page=50）",
        // 依据: Types: Tool/Material/Process
        "实体类型过滤：工具 / 材料 / 工艺（Tool / Material / Process）",
        // 依据: Select multiple → merge to target name
        "多选实体后合并至目标名称",
        // 依据: Search debounce, pagination
        "搜索防抖与分页控件",
      ],
      actions: [
        "选择实体类型并输入关键词搜索目标实体。",
        "勾选多个重复实体，填写合并目标名称后点击「合并」。",
        "使用分页控件浏览大量实体。",
      ],
      related: [
        { label: "同义词管理", href: "/admin/synonyms" },
        { label: "知识图谱", href: "/graph" },
        { label: "图谱 Schema", href: "/admin/schema" },
      ],
    },
  },

  {
    match: "/admin/associations",
    key: "/admin/associations",
    guide: {
      title: "关联关系挖掘",
      summary: "挖掘并审核实体间的潜在关联关系。",
      features: [
        // 依据: admin/associations/page.tsx, GET /api/admin/associations (mining results)
        "关联挖掘结果列表（GET /api/admin/associations）",
        // 依据: POST /api/admin/associations/run, /confirm
        "触发挖掘任务（POST /api/admin/associations/run）与确认关联（POST /confirm）",
        // 依据: Filter by status, confirm/ignore actions per association
        "按状态过滤，逐条确认或忽略",
      ],
      actions: [
        "点击「运行挖掘」启动关联分析任务。",
        "查看挖掘结果列表，逐条点击「确认」或「忽略」。",
        "按状态过滤只显示待处理的关联建议。",
      ],
      related: [
        { label: "实体管理", href: "/admin/entities" },
        { label: "数据冲突", href: "/admin/conflicts" },
        { label: "知识图谱", href: "/graph" },
      ],
    },
  },

  {
    match: "/admin/conflicts",
    key: "/admin/conflicts",
    guide: {
      title: "数据治理中心",
      summary: "扫描并处理知识库中的数据冲突问题。",
      features: [
        // 依据: admin/conflicts/page.tsx, Title "数据治理中心" with icon, scan button
        "一键扫描触发冲突检测（startScan 函数）",
        // 依据: loadConflicts(), loadStats()
        "冲突列表加载（loadConflicts）与统计加载（loadStats）",
      ],
      actions: [
        "点击「扫描」按钮触发全量冲突检测。",
        "在冲突列表中逐条查看并处理数据冲突。",
        "查看统计面板了解各类冲突的数量分布。",
      ],
      related: [
        { label: "数据质量", href: "/admin/data-quality" },
        { label: "数据治理", href: "/admin/governance" },
        { label: "关联关系挖掘", href: "/admin/associations" },
      ],
    },
  },

  {
    match: "/admin/synonyms",
    key: "/admin/synonyms",
    guide: {
      title: "同义词管理",
      summary: "维护知识库实体的同义词词典。",
      features: [
        // 依据: admin/synonyms/page.tsx, GET /api/admin/synonyms
        "同义词列表（GET /api/admin/synonyms）",
        // 依据: POST /api/admin/synonyms, DELETE /api/admin/synonyms/[term]
        "添加同义词（POST /api/admin/synonyms）与删除（DELETE /[term]）",
      ],
      actions: [
        "点击「新增」输入术语与其同义词后保存。",
        "点击列表中的删除图标移除同义词条目。",
      ],
      related: [
        { label: "实体管理", href: "/admin/entities" },
        { label: "检索权重实验室", href: "/admin/lab" },
      ],
    },
  },

  {
    match: "/admin/annotation",
    key: "/admin/annotation",
    guide: {
      title: "多模态手动补全",
      summary: "人工审核 OCR 纠错与图片描述补充任务。",
      features: [
        // 依据: admin/annotation/page.tsx L?, GET /api/annotation/pending
        "待审核任务加载（GET /api/annotation/pending）",
        // 依据: 2 tabs: 章节审核 / 图片审核, SectionReviewer, ImageReviewer
        "2 个标签页：章节审核（SectionReviewer）/ 图片审核（ImageReviewer）",
        // 依据: POST /api/annotation/batch-analyze, Cpu icon
        "批量 VLM 分析启动（POST /api/annotation/batch-analyze）",
        // 依据: exportCsv, GET /api/annotation/export-csv
        "导出待审核列表（GET /api/annotation/export-csv）",
        // 依据: Stats: 待审核章节数 / 待审核图片数 / 本次完成进度
        "会话进度统计：待审章节数 / 待审图片数 / 本次完成百分比",
      ],
      actions: [
        "点击「批量 VLM 分析」让模型自动处理图片描述。",
        "切换至「章节审核」标签人工修正 OCR 错误。",
        "切换至「图片审核」标签补充或确认图片描述。",
        "点击「导出」下载当前待审核列表 CSV 文件。",
      ],
      related: [
        { label: "批量导入管理", href: "/admin/ingest" },
        { label: "数据质量", href: "/admin/data-quality" },
      ],
    },
  },

  {
    match: "/admin/schema",
    key: "/admin/schema",
    guide: {
      title: "图谱 Schema",
      summary: "可视化查看知识图谱的节点类型与关系定义。",
      features: [
        // 依据: admin/schema/page.tsx, GET /api/graph/schema-stats
        "Schema 统计数据（GET /api/graph/schema-stats）",
        // 依据: Schema visualization with node types at fixed positions: Document, Section, Entity, Table
        "节点类型固定位置可视化：Document / Section / Entity / Table",
      ],
      actions: [
        "查看图谱中各节点类型的数量统计。",
        "查看节点间关系类型的定义与连接情况。",
      ],
      related: [
        { label: "知识图谱", href: "/graph" },
        { label: "Cypher 查询", href: "/cypher" },
        { label: "实体管理", href: "/admin/entities" },
      ],
    },
  },

  {
    match: "/admin/governance",
    key: "/admin/governance",
    guide: {
      title: "数据治理",
      summary: "合规报告与数据质量的综合治理视图。",
      features: [
        // 依据: admin/governance/page.tsx, GET /api/admin/compliance/report?days=7
        "合规报告（GET /api/admin/compliance/report?days=7）",
        // 依据: GET /api/admin/data-quality/summary
        "数据质量摘要（GET /api/admin/data-quality/summary）",
      ],
      actions: [
        "查看合规报告了解近期数据合规状态。",
        "查看数据质量摘要定位质量问题集中点。",
      ],
      related: [
        { label: "数据冲突", href: "/admin/conflicts" },
        { label: "数据质量", href: "/admin/data-quality" },
        { label: "合规仪表盘", href: "/admin/compliance" },
      ],
    },
  },

  {
    match: "/admin/lifecycle",
    key: "/admin/lifecycle",
    guide: {
      title: "生命周期管理",
      summary: "配置文档生命周期策略并触发执行。",
      features: [
        // 依据: admin/lifecycle/page.tsx, GET /api/admin/lifecycle/policies
        "策略列表（GET /api/admin/lifecycle/policies）",
        // 依据: Edit policy threshold, POST /api/admin/lifecycle/run
        "编辑策略阈值与触发运行（POST /api/admin/lifecycle/run）",
        // 依据: Results: Record<string, number>
        "运行结果展示（各策略处理文档数量）",
      ],
      actions: [
        "查看并编辑各生命周期策略的阈值参数。",
        "点击「触发运行」立即执行生命周期策略。",
        "查看运行结果了解各策略处理的文档数量。",
      ],
      related: [
        { label: "数据治理", href: "/admin/governance" },
        { label: "文档库", href: "/library" },
      ],
    },
  },

  {
    match: "/admin/data-quality",
    key: "/admin/data-quality",
    guide: {
      title: "数据质量",
      summary: "查看知识库数据质量的综合摘要报告。",
      features: [
        // 依据: admin/data-quality/page.tsx, GET /api/admin/data-quality/summary
        "数据质量摘要（GET /api/admin/data-quality/summary）",
        // 依据: Refresh button
        "手动刷新按钮",
      ],
      actions: [
        "查看数据质量摘要，关注低质量文档或章节。",
        "点击刷新按钮获取最新质量统计数据。",
      ],
      related: [
        { label: "数据治理", href: "/admin/governance" },
        { label: "数据冲突", href: "/admin/conflicts" },
        { label: "多模态补全", href: "/admin/annotation" },
      ],
    },
  },

  {
    match: "/admin/processing",
    key: "/admin/processing",
    guide: {
      title: "任务处理队列",
      summary: "监控与管理文档处理任务的执行状态。",
      features: [
        // 依据: admin/processing/page.tsx, GET /api/admin/processing/status (poll)
        "轮询处理任务状态（GET /api/admin/processing/status）",
        // 依据: POST /api/admin/processing/retry/[task_id]
        "重试失败任务（POST /api/admin/processing/retry/[task_id]）",
        // 依据: POST /api/admin/processing/clear-completed
        "清除已完成任务（POST /api/admin/processing/clear-completed）",
      ],
      actions: [
        "查看任务队列状态，定位失败或卡住的任务。",
        "点击失败任务旁的「重试」重新触发处理。",
        "点击「清除已完成」清理任务列表。",
      ],
      related: [
        { label: "批量导入管理", href: "/admin/ingest" },
        { label: "系统状态", href: "/admin/status" },
      ],
    },
  },
];
