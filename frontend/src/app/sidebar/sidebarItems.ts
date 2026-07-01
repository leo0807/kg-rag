import {
  Activity, AlertTriangle, BadgeCheck, BarChart2, BookMarked, BookOpen,
  Bot, BrainCircuit, ClipboardList, Code2, CreditCard, Cpu,
  Database, FileBarChart, FileText, FlaskConical, Gauge, GitBranch,
  Globe, HelpCircle, ImagePlay, KeyRound, Languages, Link2,
  type LucideIcon, MessageSquare, Network, Radio, ScrollText,
  Search, Server, Settings, Shield, ShieldCheck, SlidersHorizontal,
  Star, Terminal, TestTube2, TrendingUp, Upload, Users, Webhook,
} from "lucide-react";

export interface SidebarItem {
  href: string;
  label: string;
  shortcut?: string;
  Icon: LucideIcon;
}

export interface SidebarGroup {
  key: string;
  label: string;
  Icon: LucideIcon;
  items: SidebarItem[];
}

export const tier1Items: SidebarItem[] = [
  { href: "/query",     label: "智能问答", shortcut: "⌘/", Icon: MessageSquare },
  { href: "/library",   label: "文档库",   shortcut: "⌘B", Icon: BookOpen },
  { href: "/search",    label: "搜索",     shortcut: "⌘K", Icon: Search },
  { href: "/wiki",      label: "规范百科",                  Icon: Globe },
  { href: "/graph",     label: "知识图谱",                  Icon: Network },
  { href: "/graph/spo", label: "SPO 图谱",                  Icon: GitBranch },
  { href: "/favorites", label: "工作区",                    Icon: Star },
];

export const tier2Groups: SidebarGroup[] = [
  {
    key: "analysis",
    label: "分析",
    Icon: BarChart2,
    items: [
      { href: "/advanced-search", label: "高级查询", Icon: Search },
      { href: "/generation",      label: "规范生成", Icon: FileText },
      { href: "/simulation",      label: "仿真案例", Icon: TestTube2 },
      { href: "/analytics",       label: "检索分析", Icon: TrendingUp },
    ],
  },
  {
    key: "dev",
    label: "开发",
    Icon: Code2,
    items: [
      { href: "/pipeline",   label: "检索链路",   Icon: Gauge },
      { href: "/cypher",     label: "Cypher",     Icon: Terminal },
      { href: "/developers", label: "开发者门户", Icon: Code2 },
    ],
  },
];

export const adminGroups: SidebarGroup[] = [
  {
    key: "ops",
    label: "运营监控",
    Icon: Activity,
    items: [
      { href: "/admin/metrics",    label: "系统监控",     Icon: Activity },
      { href: "/admin/status",     label: "系统状态",     Icon: Server },
      { href: "/admin/dashboard",  label: "系统健康看板", Icon: Gauge },
      { href: "/admin/ops",        label: "AI 工程台",    Icon: Bot },
      { href: "/admin/processing", label: "数据处理看板", Icon: Activity },
      { href: "/realtime",         label: "实时监控",     Icon: Radio },
      { href: "/admin/ask-data",   label: "数据问答",     Icon: HelpCircle },
      { href: "/admin/logs",       label: "系统日志",     Icon: ScrollText },
      { href: "/admin/audit",      label: "审计日志",     Icon: ClipboardList },
    ],
  },
  {
    key: "quality",
    label: "数据质量",
    Icon: ShieldCheck,
    items: [
      { href: "/admin/entities",     label: "实体审核",     Icon: ShieldCheck },
      { href: "/admin/associations", label: "隐性关联挖掘", Icon: GitBranch },
      { href: "/admin/conflicts",    label: "规范冲突检测", Icon: AlertTriangle },
      { href: "/admin/synonyms",     label: "同义词词典",   Icon: Languages },
      { href: "/admin/annotation",   label: "手动补全",     Icon: ImagePlay },
      { href: "/admin/gnn",          label: "GNN 训练",     Icon: BrainCircuit },
    ],
  },
  {
    key: "eval",
    label: "评测调优",
    Icon: FlaskConical,
    items: [
      { href: "/admin/eval",      label: "测试集评测", Icon: FlaskConical },
      { href: "/admin/prompts",   label: "Prompt 管理", Icon: BookMarked },
      { href: "/admin/feedback",  label: "反馈分析",    Icon: MessageSquare },
      { href: "/admin/lab",       label: "权重实验室",  Icon: SlidersHorizontal },
      { href: "/admin/analytics", label: "活跃度报表",  Icon: BarChart2 },
      { href: "/admin/reports",   label: "报告中心",    Icon: FileBarChart },
      { href: "/admin/finetune",  label: "模型微调",    Icon: Cpu },
    ],
  },
  {
    key: "config",
    label: "系统配置",
    Icon: Settings,
    items: [
      { href: "/admin/schema",          label: "Schema",       Icon: Database },
      { href: "/admin/tenant-settings", label: "租户设置",     Icon: Settings },
      { href: "/admin/integrations",    label: "外部系统集成", Icon: Link2 },
      { href: "/admin/webhooks",        label: "Webhook",      Icon: Webhook },
      { href: "/admin/local-models",    label: "本地模型",     Icon: Cpu },
      { href: "/admin/governance",      label: "数据治理",     Icon: Shield },
      { href: "/admin/compliance",      label: "合规审计",     Icon: BadgeCheck },
      { href: "/admin/credentials",     label: "凭据管理",     Icon: KeyRound },
      { href: "/admin/ingest",          label: "数据接入",     Icon: Upload },
    ],
  },
  {
    key: "billing",
    label: "用量账单",
    Icon: CreditCard,
    items: [
      { href: "/admin/billing", label: "账单中心", Icon: CreditCard },
      { href: "/admin/quota",   label: "配额使用", Icon: BarChart2 },
      { href: "/admin/usage",   label: "用量监控", Icon: Gauge },
    ],
  },
];

export const superAdminItem: SidebarItem = {
  href: "/platform/dashboard",
  label: "平台超管",
  Icon: Users,
};
