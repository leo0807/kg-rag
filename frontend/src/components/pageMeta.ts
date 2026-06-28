import {
  Activity, AlertTriangle, BadgeCheck, BarChart2, BookMarked, BookOpen,
  Bot, BrainCircuit, ClipboardList, Code2, CreditCard, Cpu,
  Database, FileBarChart, FileText, FlaskConical, Gauge, GitBranch,
  Globe, HelpCircle, ImagePlay, KeyRound, Languages, Link2,
  type LucideIcon, MessageSquare, Network, Radio, ScrollText,
  Search, Server, Settings, Shield, ShieldCheck, SlidersHorizontal,
  Star, Terminal, TrendingUp, Upload, Users, Webhook,
} from "lucide-react";

export interface Meta { Icon: LucideIcon; title: string; desc: string; detail: string }

export const META: Record<string, Meta> = {
  "/search": {
    Icon: Search, title: "搜索", desc: "全文检索规范章节与约束条件，支持高亮关键词",
    detail: "支持对全部已导入规范文档进行全文检索，精确定位章节编号与约束条件。检索结果按相关度排序，关键词自动高亮显示，并提供原文摘要与所属文档信息，方便快速定位与跳转。",
  },
  "/wiki": {
    Icon: Globe, title: "规范百科", desc: "浏览全部规范文档，按标准体系分类查阅",
    detail: "以百科形式展示系统内全部规范文档，按标准体系（如材料工艺、装配、检测等）分类浏览。每份文档显示版本号、章节数与最近更新时间，支持点击进入文档详情页查看完整内容。",
  },
  "/favorites": {
    Icon: Star, title: "工作区", desc: "收藏的规范章节、文档与常用问题快捷入口",
    detail: "汇聚您收藏的规范章节与文档，以及历史问答记录，打造个人工作台。支持分组管理收藏内容，一键跳转目标章节，提升日常规范查阅效率。",
  },
  "/library": {
    Icon: BookOpen, title: "文档库", desc: "管理已导入的规范文档，支持版本追踪与重处理",
    detail: "集中管理所有已导入的规范文档，显示解析状态、向量入库进度与知识图谱构建结果。支持文档重处理、版本追踪与删除操作，是维护知识库数据质量的核心入口。",
  },
  "/advanced-search": {
    Icon: Search, title: "高级查询", desc: "按约束值范围、版本差异与交叉引用精确检索",
    detail: "提供三类专项查询能力：① 参数范围查询——按约束类型、单位与数值区间精确筛选参数条目；② 版本溯源——追溯文档的历史版本与替代关系；③ 跨规范引用——定位哪些章节引用了目标规范，理清标准间依赖网络。",
  },
  "/generation": {
    Icon: FileText, title: "规范生成", desc: "基于知识图谱辅助生成新规范草稿",
    detail: "结合已有规范知识图谱，辅助撰写新规范草稿或修订意见。系统自动检索相关约束条款与参考文档，生成结构化草稿供审核。适用于新工艺规范起草、版本更新说明等场景。",
  },
  "/simulation": {
    Icon: FlaskConical, title: "仿真案例", desc: "查看工艺仿真典型案例与分析结果",
    detail: "收录历次工艺仿真的典型案例，包括仿真参数配置、约束满足情况与分析结论。通过对比同类工艺参数，帮助工程师快速评估新工艺方案的合规性，为仿真决策提供参考依据。",
  },
  "/analytics": {
    Icon: TrendingUp, title: "检索分析", desc: "问答命中率、检索链路指标的统计与可视化",
    detail: "多维度可视化系统检索效果指标，包括问答命中率、向量/图谱/BM25 各路召回贡献比例、平均响应延迟与用户满意度趋势。帮助运营人员识别检索瓶颈，指导 Prompt 与权重调优。",
  },
  "/cypher": {
    Icon: Terminal, title: "Cypher 控制台", desc: "直接在 Neo4j 知识图谱上执行 Cypher 查询",
    detail: "提供 Neo4j 图数据库的 Cypher 查询界面，支持自由探索实体关系、验证图谱结构与调试查询语句。内置 Cypher 语法高亮与结果格式化，同时提供管理员批量执行模式，适合数据治理与图谱维护场景。",
  },
  "/developers": {
    Icon: Code2, title: "开发者门户", desc: "REST API 文档、SDK 示例与接入指南",
    detail: "面向集成开发者提供完整的 API 参考文档，包括所有端点的请求/响应示例、鉴权说明与速率限制说明。附有 Python/TypeScript SDK 代码示例，以及 MCP 协议接入指引，助力系统集成与二次开发。",
  },
  "/settings": {
    Icon: Settings, title: "设置", desc: "个人信息、密码修改与界面偏好配置",
    detail: "管理个人账户信息（工号、姓名、邮箱），修改登录密码，以及配置界面偏好（主题、语言、侧边栏折叠等）。管理员用户可在此查看账户权限范围，普通用户仅能修改本人信息。",
  },
  "/notes": {
    Icon: ScrollText, title: "我的笔记", desc: "阅读规范时留下的批注与个人笔记",
    detail: "在阅读规范文档过程中随时记录批注与心得，支持 Markdown 格式编辑。每条笔记可关联具体章节，并打上自定义标签，便于后续检索。支持导出为 PDF 或 Markdown 文件，方便离线归档。",
  },
  "/references": {
    Icon: Link2, title: "引用关系", desc: "规范章节间引用依赖的图谱视图",
    detail: "以力导向图可视化展示规范文档间的引用依赖网络，支持按文档 ID 聚焦并展开 1-2 跳邻居节点。可切换显示 AI 挖掘的隐性语义关联（虚线），辅助识别标准间潜在的间接依赖关系。",
  },
  "/realtime": {
    Icon: Radio, title: "实时监控", desc: "进行中的处理任务与后台流式输出",
    detail: "实时展示后台正在执行的文档解析、图谱构建与向量入库任务的进度流，支持 SSE 流式日志输出。可查看各步骤耗时与当前处理的 chunk 详情，便于判断长时间任务的运行状态。",
  },
  "/ingest": {
    Icon: Upload, title: "数据导入", desc: "上传并解析规范文档，触发知识图谱构建",
    detail: "支持批量上传 PDF/Word/TXT 格式的规范文档，自动触发 OCR 解析、章节拆分、实体抽取与向量入库全流程。可配置解析参数（如 chunk 大小）并实时监控处理进度，是扩展知识库的主要入口。",
  },
  "/graph": {
    Icon: Network, title: "知识图谱", desc: "可视化探索规范实体与工艺流程的关联图谱",
    detail: "以交互式图谱展示航空工艺知识体系，涵盖规范实体、工艺参数、材料与设备之间的多类型关系。支持节点筛选、关系类型过滤与路径搜索，也可切换为树状、矩阵或桑基图等多种可视化布局。",
  },
  "/admin/metrics": {
    Icon: Activity, title: "系统监控", desc: "请求量、延迟、错误率的实时曲线与告警",
    detail: "实时绘制 API 请求量、P50/P95 响应延迟、错误率及 LLM Token 消耗曲线。支持配置阈值告警规则（如错误率 > 5% 时邮件通知），并展示最近 24 小时的趋势变化与异常时段。",
  },
  "/admin/status": {
    Icon: Server, title: "系统状态", desc: "各服务健康状态与基础组件依赖检查",
    detail: "汇总展示所有依赖服务（PostgreSQL、Neo4j、Milvus、Redis、Elasticsearch）的当前健康状态与连接延迟。每 30 秒自动刷新，异常服务以红色警告标记，便于快速定位基础设施故障。",
  },
  "/admin/dashboard": {
    Icon: Gauge, title: "健康看板", desc: "综合展示 API / 图谱 / 向量库运行指标",
    detail: "运维综合看板，将 API 吞吐量、知识图谱节点/边数、向量库索引规模与查询延迟整合到一个页面。适合值班工程师日常巡检，快速把握系统整体健康度。",
  },
  "/admin/ops": {
    Icon: Bot, title: "AI 工程台", desc: "在线调试检索链路、Prompt 与模型参数",
    detail: "提供端到端检索链路调试能力：输入任意问题后可逐步查看向量召回结果、图谱扩展节点、Prompt 组装内容与最终 LLM 响应。支持实时修改 Prompt 模板与模型参数并立即对比效果，是 RAG 调优的核心工具。",
  },
  "/admin/processing": {
    Icon: Activity, title: "数据处理看板", desc: "文档解析、图谱构建与向量入库进度追踪",
    detail: "汇总展示所有文档的处理状态：待处理、解析中、图谱构建、向量入库与已完成。每个阶段均显示已处理/总数与耗时，支持重新触发失败任务。适合批量导入时的整体进度监控。",
  },
  "/admin/ask-data": {
    Icon: HelpCircle, title: "数据问答", desc: "以自然语言查询结构化运营指标与日志",
    detail: "将运营数据库开放给自然语言查询，由 LLM 自动将问题转换为 SQL 并返回结果。例如：「上周 API 错误最多的端点是什么？」系统自动检索日志数据库并以表格形式呈现分析结果。",
  },
  "/admin/logs": {
    Icon: ScrollText, title: "系统日志", desc: "实时滚动查看服务端运行日志流",
    detail: "通过 SSE 流式接口实时展示后端各服务的运行日志，支持按日志级别（DEBUG/INFO/WARNING/ERROR）过滤与关键词搜索。日志自动滚动，可暂停查看历史记录，适合问题排查与实时监控。",
  },
  "/admin/audit": {
    Icon: ClipboardList, title: "审计日志", desc: "用户操作行为、访问记录与安全事件审计",
    detail: "记录所有用户的关键操作，包括登录/退出、文档上传、参数修改与管理员操作，满足等保 2.0 审计要求。支持按用户、时间范围、操作类型过滤，并可导出为 CSV 备查。",
  },
  "/admin/entities": {
    Icon: ShieldCheck, title: "实体审核", desc: "人工审核 AI 自动抽取的图谱实体质量",
    detail: "展示 AI 自动从规范文档中抽取的实体条目（如材料名称、工艺参数、设备型号），供人工逐条审核。审核人员可标记「确认」「修正」「拒绝」，结果反馈至图谱训练闭环，持续提升抽取准确率。",
  },
  "/admin/associations": {
    Icon: GitBranch, title: "隐性关联挖掘", desc: "发现规范条目之间隐含的语义关联关系",
    detail: "利用向量相似度与图神经网络，在已有显式引用关系之外，挖掘规范章节之间的隐性语义关联（如不同规范中对同一参数的不同表述）。挖掘结果可供审核确认后写入知识图谱，丰富关系网络。",
  },
  "/admin/conflicts": {
    Icon: AlertTriangle, title: "冲突检测", desc: "检测并标记不同规范版本间的矛盾条款",
    detail: "自动比对同一工艺领域的多份规范中相同参数的约束值，标记存在数值矛盾或逻辑冲突的条款组合。冲突列表按严重程度排序，供规范管理员审查并决定采纳哪份规范为基准。",
  },
  "/admin/synonyms": {
    Icon: Languages, title: "同义词词典", desc: "维护领域术语的同义词、别名与缩写映射",
    detail: "管理航空工艺领域的专有名词同义词表，包括中英文别名、常见缩写与俗称映射（如「铆接」=「铆合」=\"Riveting\"）。同义词词典直接影响全文检索召回率，定期更新可显著提升检索覆盖度。",
  },
  "/admin/annotation": {
    Icon: ImagePlay, title: "手动补全", desc: "对未识别内容进行人工标注与图谱补全",
    detail: "针对 AI 自动化流程未能正确识别的图表、公式或特殊排版内容，提供人工标注界面。标注员可直接在原始页面截图上绘制标注框并填写结构化内容，标注结果自动回流至图谱，补全知识盲区。",
  },
  "/admin/gnn": {
    Icon: BrainCircuit, title: "GNN 训练", desc: "训练图神经网络提升实体关联推理能力",
    detail: "在已积累的知识图谱数据上训练图神经网络（如 GraphSAGE），增强实体关联推理与链接预测能力。可配置训练集比例、模型超参与训练轮次，训练完成后自动部署用于图谱增强检索。",
  },
  "/admin/eval": {
    Icon: FlaskConical, title: "测试集评测", desc: "使用黄金标注集评估问答系统准确率",
    detail: "加载预置的黄金标注问答对（含标准答案与参考 chunk），批量运行系统并计算 Recall@K、MRR、BLEU、ROUGE 等指标。评测报告可与历史版本对比，用于验证每次优化是否带来实际提升。",
  },
  "/admin/prompts": {
    Icon: BookMarked, title: "Prompt 管理", desc: "版本化管理系统与用户端 Prompt 模板",
    detail: "对系统内所有 Prompt 模板（检索增强、摘要生成、实体抽取等）进行版本化管理，支持 A/B 版本对比测试。每个版本记录修改人、修改时间与效果指标，支持一键回滚到历史版本。",
  },
  "/admin/feedback": {
    Icon: MessageSquare, title: "反馈分析", desc: "统计用户点踩 / 点赞与文字反馈分布",
    detail: "汇总用户对问答结果的满意度反馈（点赞/点踩/评论），按时间、问题类型与用户角色多维度统计分布。不满意的反馈自动关联到对应的检索链路记录，便于定位待优化的问答场景。",
  },
  "/admin/lab": {
    Icon: SlidersHorizontal, title: "权重实验室", desc: "实验性调节向量 / BM25 / 图谱检索融合权重",
    detail: "提供可视化滑块实时调节混合检索（向量/BM25/图谱）各路权重，即时展示权重变化对测试问题的检索结果影响。实验结果自动记录到日志，便于找到最优融合策略后一键应用到生产配置。",
  },
  "/admin/analytics": {
    Icon: BarChart2, title: "活跃度报表", desc: "用户活跃度、使用频次与功能分布统计",
    detail: "展示各功能模块的日活/月活用户数、问答次数、文档检索频次与平均会话时长等运营指标。按用户角色与部门细分，辅助产品决策与资源规划。",
  },
  "/admin/reports": {
    Icon: FileBarChart, title: "报告中心", desc: "生成并下载系统评测与运营周期报告",
    detail: "一键生成系统运营周报/月报，内容涵盖检索效果指标、用户活跃度、错误率趋势与重要事件汇总。支持 PDF/Excel 导出格式，可定时自动生成并发送至管理员邮箱。",
  },
  "/admin/finetune": {
    Icon: Cpu, title: "模型微调", desc: "基于航空领域数据微调 Qwen / Embedding 模型",
    detail: "使用积累的领域问答对与实体标注数据，对 Qwen 大语言模型及 Embedding 模型进行 LoRA 微调。可配置微调参数、监控训练损失曲线，微调完成后在评测集上验证效果再决定是否上线。",
  },
  "/admin/schema": {
    Icon: Database, title: "Schema 管理", desc: "查看并同步 PostgreSQL 表结构与索引",
    detail: "展示当前 PostgreSQL 数据库中所有表的结构、字段类型与索引定义，并与 SQLAlchemy ORM 模型进行比对。检测到 Schema 漂移时，可在此安全触发同步（仅补充缺失表，不修改已有结构）。",
  },
  "/admin/tenant-settings": {
    Icon: Settings, title: "租户设置", desc: "配置租户名称、功能开关与资源限额",
    detail: "在多租户模式下管理当前租户的基本信息（名称、LOGO、联系人）、功能模块开关与资源配额（最大文档数、Token 月限额）。配置变更即时生效，无需重启服务。",
  },
  "/admin/integrations": {
    Icon: Link2, title: "外部集成", desc: "配置与 MES / PLM / ERP 系统的数据互联",
    detail: "提供与工厂 MES、PLM（CATIA/Teamcenter）、ERP 系统的数据接口配置界面。支持设置 API Base URL、鉴权方式与字段映射，并提供连通性测试，实现规范数据的实时双向同步。",
  },
  "/admin/webhooks": {
    Icon: Webhook, title: "Webhook", desc: "订阅系统事件并推送至外部 HTTP 端点",
    detail: "管理系统 Webhook 订阅，可选择订阅文档处理完成、告警触发、用户操作等事件类型，配置目标 URL 与签名密钥后，系统会在事件发生时自动推送 JSON payload，并提供推送历史与重试机制。",
  },
  "/admin/local-models": {
    Icon: Cpu, title: "本地模型", desc: "管理本地部署的 LLM 与 Embedding 推理服务",
    detail: "统一管理本地或私有云上部署的推理服务（如 Ollama、vLLM、Triton），配置模型名称、端点地址与并发限制。支持健康检查与负载均衡，可在此切换生产环境使用的模型版本。",
  },
  "/admin/governance": {
    Icon: Shield, title: "数据治理", desc: "数据血缘、脱敏策略与生命周期管理",
    detail: "提供数据血缘追踪（文档 → chunk → 向量 → 问答记录）、敏感字段脱敏规则配置与数据保留期限策略设置。满足企业数据安全合规要求，确保知识库数据的可追溯性与完整生命周期管理。",
  },
  "/admin/compliance": {
    Icon: BadgeCheck, title: "合规审计", desc: "满足等保 2.0 与数据安全法规的审计能力",
    detail: "提供等保 2.0 三级合规所需的审计能力，包括操作日志不可篡改存储、异常访问告警、敏感数据访问记录与定期合规报告生成。可对接外部 SIEM 系统，支持证据留存与合规检查清单。",
  },
  "/admin/credentials": {
    Icon: KeyRound, title: "凭据管理", desc: "API Key 与第三方服务凭据的安全集中管理",
    detail: "集中管理系统使用的所有 API Key（OpenAI、Qwen、Embedding 服务等）及第三方系统凭据，采用加密存储与最小权限原则。支持 Key 轮换、访问日志与到期提醒，避免凭据硬编码带来的安全风险。",
  },
  "/admin/ingest": {
    Icon: Upload, title: "数据接入", desc: "配置并触发规范文档的批量自动导入",
    detail: "管理端的数据导入中心，支持配置自动扫描目录（NFS/S3/本地）并定时批量导入规范文档。可设置文件过滤规则、解析参数与优先级队列，并查看历次批量导入的成功率与耗时统计。",
  },
  "/admin/billing": {
    Icon: CreditCard, title: "账单中心", desc: "查看 Token 用量统计与费用明细",
    detail: "展示按月/周/日统计的 LLM Token 消耗量与推算费用，细分到各模型（GPT-4/Qwen/Embedding）。支持设置月度预算上限与告警阈值，费用超限时自动限流并通知管理员，控制运营成本。",
  },
  "/admin/quota": {
    Icon: BarChart2, title: "配额使用", desc: "各用户与租户的用量配额消耗状态",
    detail: "展示每个用户与租户当月的 API 调用次数、Token 消耗量与文档存储量占配额的比例，支持超额预警与手动调整配额上限。方便管理员合理分配资源，避免单一用户占用过多系统资源。",
  },
  "/admin/usage": {
    Icon: Gauge, title: "用量监控", desc: "实时跟踪 API 调用频率与速率限制告警",
    detail: "实时监控 API 调用速率（QPS）并与速率限制阈值对比，当请求接近限制时提前告警。可查看各端点的调用频率分布与峰值时段，辅助调整限流策略与容量规划。",
  },
  "/platform/dashboard": {
    Icon: Users, title: "平台超管", desc: "跨租户平台级管理与全局配置",
    detail: "平台级超级管理员控制台，可查看所有租户的用量概况、创建/暂停/删除租户、管理全局系统配置（如默认模型、全局速率限制）。变更操作均记录审计日志，权限仅限平台管理员角色。",
  },
};

export const SKIP = new Set(["/query", "/pipeline"]);
