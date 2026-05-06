"use client";

import {
  AlertTriangle,
  BarChart2,
  BookOpen,
  Bot,
  BrainCircuit,
  ChevronLeft,
  ChevronRight,
  ClipboardList,
  FlaskConical,
  ImagePlay,
  Gauge,
  Activity,
  Database,
  Languages,
  SlidersHorizontal,
  GitBranch,
  GitCompare,
  LogOut,
  MessageSquare,
  Network,
  Search,
  Server,
  Settings,
  Share2,
  ShieldCheck,
  Star,
  Terminal,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useFavorites } from "@/app/favorites/useFavorites";
import ThemeToggle from "@/components/ThemeToggle";

const navItems = [
  { href: "/library", label: "文档库", shortcut: "⌘B", Icon: BookOpen },
  { href: "/search", label: "全局搜索", shortcut: "⌘K", Icon: Search },
  { href: "/query", label: "智能问答", shortcut: "⌘/", Icon: MessageSquare },
  { href: "/pipeline", label: "检索链路", shortcut: "", Icon: Gauge },
  { href: "/graph", label: "图谱可视化", shortcut: "", Icon: Network },
  {
    href: "/graph/builder",
    label: "Cypher 构造器",
    shortcut: "",
    Icon: GitBranch,
  },
  { href: "/references", label: "引用关系", shortcut: "", Icon: Share2 },
  { href: "/timeline", label: "版本时间线", shortcut: "", Icon: GitBranch },
  { href: "/compare", label: "文档对比", shortcut: "", Icon: GitCompare },
  { href: "/favorites", label: "收藏夹", shortcut: "", Icon: Star },
  {
    href: "/admin/entities",
    label: "实体审核",
    shortcut: "",
    Icon: ShieldCheck,
  },
  { href: "/admin/status", label: "系统状态", shortcut: "", Icon: Server },
  { href: "/admin/ops", label: "AI 工程台", shortcut: "", Icon: Bot },
  { href: "/admin/gnn", label: "GNN 训练", shortcut: "", Icon: BrainCircuit },
  {
    href: "/admin/analytics",
    label: "活跃度报表",
    shortcut: "",
    Icon: BarChart2,
  },
  {
    href: "/admin/eval",
    label: "测试集评测",
    shortcut: "",
    Icon: FlaskConical,
  },
  { href: "/admin/associations", label: "隐性关联挖掘", shortcut: "", Icon: GitBranch },
  {
    href: "/admin/conflicts",
    label: "规范冲突检测",
    shortcut: "",
    Icon: AlertTriangle,
  },
  {
    href: "/admin/cypher",
    label: "Cypher 执行器",
    shortcut: "",
    Icon: Terminal,
  },
  { href: "/settings", label: "设置", shortcut: "", Icon: Settings },
];

interface UserInfo {
  username: string;
  full_name: string;
  department: string;
  is_admin?: boolean;
}

const STORAGE_KEY = "sidebar_collapsed";

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<UserInfo | null>(null);
  const [collapsed, setCollapsed] = useState(false);
  const { favorites } = useFavorites();

  useEffect(() => {
    if (localStorage.getItem(STORAGE_KEY) === "1") setCollapsed(true);
  }, []);

  useEffect(() => {
    function syncUser() {
      const stored = localStorage.getItem("user");
      if (!stored) {
        setUser(null);
        return;
      }
      try {
        setUser(JSON.parse(stored));
      } catch { }
    }

    syncUser();
    window.addEventListener("user-updated", syncUser as EventListener);
    window.addEventListener("storage", syncUser);
    return () => {
      window.removeEventListener("user-updated", syncUser as EventListener);
      window.removeEventListener("storage", syncUser);
    };
  }, []);

  function toggle() {
    setCollapsed((v) => {
      const next = !v;
      localStorage.setItem(STORAGE_KEY, next ? "1" : "0");
      return next;
    });
  }

  function isActive(href: string) {
    if (pathname === href) return true;
    // 如果当前路径以某个 href 开头，我们需要检查是否有更精确（更长）的匹配项在导航栏中
    if (pathname.startsWith(`${href}/`)) {
      const hasMoreSpecificMatch = navItems.some(
        (item) =>
          item.href !== href &&
          item.href.length > href.length &&
          pathname.startsWith(item.href),
      );
      return !hasMoreSpecificMatch;
    }
    return false;
  }

  function handleLogout() {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    router.push("/login");
  }

  return (
    <aside
      className={`flex-shrink-0 border-r flex flex-col transition-all duration-200 ${collapsed ? "w-14" : "w-44"}`}
      style={{ background: "var(--nav-bg)", borderColor: "var(--nav-border)" }}
    >
      {/* Logo + 折叠按钮 */}
      <div className="flex items-center justify-between px-3 py-4 min-h-[60px]"
        style={{ borderBottom: "1px solid var(--nav-border)" }}>
        {!collapsed && (
          <div>
            <div className="text-sm font-bold leading-tight" style={{ color: "var(--nav-text)" }}>
              商飞大模型
            </div>
            <div className="text-xs mt-0.5" style={{ color: "var(--nav-text-muted)" }}>航空工艺规范</div>
          </div>
        )}
        <button
          type="button"
          onClick={toggle}
          className={`p-1.5 rounded-lg hover:bg-white/10
                                transition-colors flex-shrink-0 ${collapsed ? "mx-auto" : "ml-auto"}`}
          style={{ color: "var(--nav-text-muted)" }}
          title={collapsed ? "展开菜单" : "折叠菜单"}
        >
          {collapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
        </button>
      </div>

      {/* 导航（可滚动，flex-1 撑满剩余空间） */}
      <nav className="flex-1 overflow-y-auto px-2 py-3 space-y-0.5">
        {navItems.map(({ href, label, shortcut, Icon }) => {
          const active = isActive(href);
          const badge =
            href === "/favorites" && favorites.length > 0
              ? favorites.length
              : 0;
          return (
            <Link
              key={href}
              href={href}
              title={
                collapsed
                  ? `${label}${shortcut ? `  ${shortcut}` : ""}`
                  : undefined
              }
              className={`flex items-center gap-2.5 rounded-lg text-sm
                                        transition-colors group
                                        ${collapsed ? "justify-center px-0 py-2.5" : "px-3 py-2"}
                                        ${active
                  ? "bg-[var(--nav-active-bg)] text-[var(--nav-text)]"
                  : "text-[var(--nav-text-muted)] hover:text-[var(--nav-text)] hover:bg-white/10"
                }`}
            >
              <div className="relative flex-shrink-0">
                <Icon size={15} />
                {badge > 0 && collapsed && (
                  <span
                    className="absolute -top-1 -right-1 w-3.5 h-3.5 bg-amber-500 rounded-full
                                                     flex items-center justify-center text-[8px] text-white font-bold"
                  >
                    {badge > 9 ? "9+" : badge}
                  </span>
                )}
              </div>
              {!collapsed && (
                <>
                  <span className="flex-1">{label}</span>
                  {badge > 0 && (
                    <span
                      className="px-1.5 py-0.5 bg-amber-500/20 text-amber-400
                                                         text-[10px] font-bold rounded-full"
                    >
                      {badge}
                    </span>
                  )}
                  {shortcut && badge === 0 && (
                    <span
                      className="text-xs font-mono"
                      style={{ color: active ? "rgba(255,255,255,0.6)" : "var(--nav-text-muted)" }}
                    >
                      {shortcut}
                    </span>
                  )}
                </>
              )}
            </Link>
          );
        })}
      </nav>

      {/* 管理员专属：用量监控（固定在可滚动区之外） */}
      {user?.is_admin && (
        <div className="flex-shrink-0 px-2 pb-1">
          {!collapsed && (
            <div className="text-[10px] uppercase tracking-wider px-3 py-1" style={{ color: "var(--nav-text-muted)" }}>Admin</div>
          )}
          <Link
            href="/admin/synonyms"
            title={collapsed ? "同义词词典" : undefined}
            className={`flex items-center gap-2.5 rounded-lg text-sm transition-colors
              ${collapsed ? "justify-center px-0 py-2.5" : "px-3 py-2"}
              ${isActive("/admin/synonyms")
                ? "bg-[var(--nav-active-bg)] text-[var(--nav-text)]"
                : "text-[var(--nav-text-muted)] hover:text-[var(--nav-text)] hover:bg-white/10"
              }`}
          >
            <Languages size={15} />
            {!collapsed && <span className="flex-1">同义词词典</span>}
          </Link>
          <Link
            href="/admin/usage"
            title={collapsed ? "用量监控" : undefined}
            className={`flex items-center gap-2.5 rounded-lg text-sm transition-colors
              ${collapsed ? "justify-center px-0 py-2.5" : "px-3 py-2"}
              ${isActive("/admin/usage")
                ? "bg-[var(--nav-active-bg)] text-[var(--nav-text)]"
                : "text-[var(--nav-text-muted)] hover:text-[var(--nav-text)] hover:bg-white/10"
              }`}
          >
            <Gauge size={15} />
            {!collapsed && <span className="flex-1">用量监控</span>}
          </Link>
          <Link
            href="/admin/annotation"
            title={collapsed ? "手动补全" : undefined}
            className={`flex items-center gap-2.5 rounded-lg text-sm transition-colors
              ${collapsed ? "justify-center px-0 py-2.5" : "px-3 py-2"}
              ${isActive("/admin/annotation")
                ? "bg-[var(--nav-active-bg)] text-[var(--nav-text)]"
                : "text-[var(--nav-text-muted)] hover:text-[var(--nav-text)] hover:bg-white/10"
              }`}
          >
            <ImagePlay size={15} />
            {!collapsed && <span className="flex-1">手动补全</span>}
          </Link>
          <Link
            href="/admin/audit"
            title={collapsed ? "审计日志" : undefined}
            className={`flex items-center gap-2.5 rounded-lg text-sm transition-colors
              ${collapsed ? "justify-center px-0 py-2.5" : "px-3 py-2"}
              ${isActive("/admin/audit")
                ? "bg-[var(--nav-active-bg)] text-[var(--nav-text)]"
                : "text-[var(--nav-text-muted)] hover:text-[var(--nav-text)] hover:bg-white/10"
              }`}
          >
            <ClipboardList size={15} />
            {!collapsed && <span className="flex-1">审计日志</span>}
          </Link>
          <Link
            href="/admin/lab"
            title={collapsed ? "权重实验室" : undefined}
            className={`flex items-center gap-2.5 rounded-lg text-sm transition-colors
              ${collapsed ? "justify-center px-0 py-2.5" : "px-3 py-2"}
              ${isActive("/admin/lab")
                ? "bg-[var(--nav-active-bg)] text-[var(--nav-text)]"
                : "text-[var(--nav-text-muted)] hover:text-[var(--nav-text)] hover:bg-white/10"
              }`}
          >
            <SlidersHorizontal size={15} />
            {!collapsed && <span className="flex-1">权重实验室</span>}
          </Link>
          <Link
            href="/admin/dashboard"
            title={collapsed ? "系统健康看板" : undefined}
            className={`flex items-center gap-2.5 rounded-lg text-sm transition-colors
              ${collapsed ? "justify-center px-0 py-2.5" : "px-3 py-2"}
              ${isActive("/admin/dashboard")
                ? "bg-[var(--nav-active-bg)] text-[var(--nav-text)]"
                : "text-[var(--nav-text-muted)] hover:text-[var(--nav-text)] hover:bg-white/10"
              }`}
          >
            <Gauge size={15} />
            {!collapsed && <span className="flex-1">健康看板</span>}
          </Link>
          <Link
            href="/admin/processing"
            title={collapsed ? "数据处理看板" : undefined}
            className={`flex items-center gap-2.5 rounded-lg text-sm transition-colors
              ${collapsed ? "justify-center px-0 py-2.5" : "px-3 py-2"}
              ${isActive("/admin/processing")
                ? "bg-[var(--nav-active-bg)] text-[var(--nav-text)]"
                : "text-[var(--nav-text-muted)] hover:text-[var(--nav-text)] hover:bg-white/10"
              }`}
          >
            <Activity size={15} />
            {!collapsed && <span className="flex-1">处理看板</span>}
          </Link>
          <Link
            href="/admin/schema"
            title={collapsed ? "Schema 导航器" : undefined}
            className={`flex items-center gap-2.5 rounded-lg text-sm transition-colors
              ${collapsed ? "justify-center px-0 py-2.5" : "px-3 py-2"}
              ${isActive("/admin/schema")
                ? "bg-[var(--nav-active-bg)] text-[var(--nav-text)]"
                : "text-[var(--nav-text-muted)] hover:text-[var(--nav-text)] hover:bg-white/10"
              }`}
          >
            <Database size={15} />
            {!collapsed && <span className="flex-1">Schema</span>}
          </Link>
        </div>
      )}

      {/* 快捷键提示（展开时显示，固定底部） */}
      {!collapsed && (
        <div className="flex-shrink-0 px-4 py-2" style={{ borderTop: "1px solid var(--nav-border)" }}>
          <div className="text-xs space-y-0.5" style={{ color: "var(--nav-text-muted)" }}>
            <div className="flex justify-between">
              <span>搜索</span>
              <span className="font-mono">⌘K</span>
            </div>
            <div className="flex justify-between">
              <span>问答</span>
              <span className="font-mono">⌘/</span>
            </div>
          </div>
        </div>
      )}

      {/* 底部用户 + 操作（固定底部，不被导航列表挤出） */}
      <div className="flex-shrink-0" style={{ borderTop: "1px solid var(--nav-border)" }}>
        {!collapsed && user && (
          <div className="px-4 py-3" style={{ borderBottom: "1px solid var(--nav-border)" }}>
            <div className="text-xs font-medium truncate" style={{ color: "var(--nav-text)" }}>
              {user.full_name || user.username}
            </div>
            <div className="text-xs mt-0.5 truncate" style={{ color: "var(--nav-text-muted)" }}>
              {user.department}
            </div>
          </div>
        )}
        <div
          className={`py-3 flex items-center gap-2
                                 ${collapsed ? "flex-col justify-center px-0" : "px-4 justify-between"}`}
        >
          {!collapsed && <div className="text-xs" style={{ color: "var(--nav-text-muted)" }}>v1.0.0</div>}
          <ThemeToggle />
          <button
            type="button"
            onClick={handleLogout}
            className="p-1.5 rounded-lg hover:text-red-400 hover:bg-white/10 transition-colors"
            style={{ color: "var(--nav-text-muted)" }}
            title="退出登录"
          >
            <LogOut size={15} />
          </button>
        </div>
      </div>
    </aside>
  );
}
