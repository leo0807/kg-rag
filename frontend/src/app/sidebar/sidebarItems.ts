import {
  Activity,
  AlertTriangle,
  BarChart2,
  BookOpen,
  Bot,
  BrainCircuit,
  ClipboardList,
  Database,
  FlaskConical,
  Gauge,
  GitBranch,
  GitCompare,
  ImagePlay,
  Languages,
  type LucideIcon,
  MessageSquare,
  Network,
  Search,
  Server,
  Settings,
  Share2,
  ShieldCheck,
  SlidersHorizontal,
  Star,
  Terminal,
} from "lucide-react";

export interface SidebarItem {
  href: string;
  label: string;
  shortcut?: string;
  Icon: LucideIcon;
}

export const mainNavItems: SidebarItem[] = [
  { href: "/library", label: "文档库", shortcut: "⌘B", Icon: BookOpen },
  { href: "/search", label: "全局搜索", shortcut: "⌘K", Icon: Search },
  { href: "/query", label: "智能问答", shortcut: "⌘/", Icon: MessageSquare },
  { href: "/pipeline", label: "检索链路", Icon: Gauge },
  { href: "/graph", label: "图谱可视化", Icon: Network },
  { href: "/cypher", label: "Cypher 工具", Icon: Terminal },
  { href: "/references", label: "引用关系", Icon: Share2 },
  { href: "/timeline", label: "版本时间线", Icon: GitBranch },
  { href: "/compare", label: "文档对比", Icon: GitCompare },
  { href: "/favorites", label: "收藏夹", Icon: Star },
  { href: "/admin/entities", label: "实体审核", Icon: ShieldCheck },
  { href: "/admin/status", label: "系统状态", Icon: Server },
  { href: "/admin/ops", label: "AI 工程台", Icon: Bot },
  { href: "/admin/gnn", label: "GNN 训练", Icon: BrainCircuit },
  { href: "/admin/analytics", label: "活跃度报表", Icon: BarChart2 },
  { href: "/admin/eval", label: "测试集评测", Icon: FlaskConical },
  { href: "/admin/prompts", label: "Prompt 管理", Icon: ClipboardList },
  { href: "/admin/associations", label: "隐性关联挖掘", Icon: GitBranch },
  { href: "/admin/conflicts", label: "规范冲突检测", Icon: AlertTriangle },
  { href: "/settings", label: "设置", Icon: Settings },
];

export const adminNavItems: SidebarItem[] = [
  { href: "/admin/synonyms", label: "同义词词典", Icon: Languages },
  { href: "/admin/usage", label: "用量监控", Icon: Gauge },
  { href: "/admin/annotation", label: "手动补全", Icon: ImagePlay },
  { href: "/admin/audit", label: "审计日志", Icon: ClipboardList },
  { href: "/admin/lab", label: "权重实验室", Icon: SlidersHorizontal },
  { href: "/admin/dashboard", label: "系统健康看板", Icon: Gauge },
  { href: "/admin/processing", label: "数据处理看板", Icon: Activity },
  { href: "/admin/schema", label: "Schema", Icon: Database },
];
