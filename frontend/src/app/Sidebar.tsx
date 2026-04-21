"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import Link from "next/link";
import ThemeToggle from "@/components/ThemeToggle";
import {
    LogOut, BookOpen, Search, MessageSquare,
    Network, GitCompare, Settings, ChevronLeft, ChevronRight, ShieldCheck, GitBranch, BrainCircuit, BarChart2, Share2, Star, Server, Activity, FlaskConical,
} from "lucide-react";
import { useFavorites } from "@/app/favorites/useFavorites";

const navItems = [
    { href: "/library",             label: "文档库",     shortcut: "⌘B", Icon: BookOpen     },
    { href: "/search",              label: "全局搜索",   shortcut: "⌘K", Icon: Search       },
    { href: "/query",               label: "智能问答",   shortcut: "⌘/", Icon: MessageSquare},
    { href: "/graph",               label: "图谱可视化", shortcut: "",   Icon: Network      },
    { href: "/graph/builder",       label: "Cypher 构造器", shortcut: "", Icon: GitBranch    },
    { href: "/references",          label: "引用关系",   shortcut: "",   Icon: Share2       },
    { href: "/timeline",            label: "版本时间线", shortcut: "",   Icon: GitBranch    },
    { href: "/compare",             label: "文档对比",   shortcut: "",   Icon: GitCompare   },
    { href: "/favorites",           label: "收藏夹",     shortcut: "",   Icon: Star         },
    { href: "/admin/entities",      label: "实体审核",   shortcut: "",   Icon: ShieldCheck  },
    { href: "/admin/status",        label: "系统状态",   shortcut: "",   Icon: Server       },
    { href: "/admin/gnn",           label: "GNN 训练",   shortcut: "",   Icon: BrainCircuit },
    { href: "/admin/analytics",     label: "活跃度报表", shortcut: "",   Icon: BarChart2    },
    { href: "/admin/eval",          label: "测试集评测", shortcut: "",   Icon: FlaskConical },
    { href: "/settings",            label: "设置",       shortcut: "",   Icon: Settings     },
];

interface UserInfo { username: string; full_name: string; department: string; }

const STORAGE_KEY = "sidebar_collapsed";

export default function Sidebar() {
    const pathname = usePathname();
    const router   = useRouter();
    const [user,      setUser]      = useState<UserInfo | null>(null);
    const [collapsed, setCollapsed] = useState(false);
    const { favorites } = useFavorites();

    useEffect(() => {
        if (localStorage.getItem(STORAGE_KEY) === "1") setCollapsed(true);
    }, []);

    useEffect(() => {
        const stored = localStorage.getItem("user");
        if (stored) { try { setUser(JSON.parse(stored)); } catch { } }
    }, []);

    function toggle() {
        setCollapsed(v => {
            const next = !v;
            localStorage.setItem(STORAGE_KEY, next ? "1" : "0");
            return next;
        });
    }

    function isActive(href: string) {
        if (pathname === href) return true;
        // 如果当前路径以某个 href 开头，我们需要检查是否有更精确（更长）的匹配项在导航栏中
        if (pathname.startsWith(href + "/")) {
            const hasMoreSpecificMatch = navItems.some(item => 
                item.href !== href && 
                item.href.length > href.length && 
                pathname.startsWith(item.href)
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
        <aside className={`flex-shrink-0 bg-gray-950 border-r border-gray-800 flex flex-col
                           transition-all duration-200 ${collapsed ? "w-14" : "w-44"}`}>

            {/* Logo + 折叠按钮 */}
            <div className="flex items-center justify-between px-3 py-4 border-b border-gray-800 min-h-[60px]">
                {!collapsed && (
                    <div>
                        <div className="text-sm font-bold text-white leading-tight">CPS 知识库</div>
                        <div className="text-xs text-gray-500 mt-0.5">航空工艺规范</div>
                    </div>
                )}
                <button
                    onClick={toggle}
                    className={`p-1.5 rounded-lg text-gray-500 hover:text-white hover:bg-gray-800
                                transition-colors flex-shrink-0 ${collapsed ? "mx-auto" : "ml-auto"}`}
                    title={collapsed ? "展开菜单" : "折叠菜单"}
                >
                    {collapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
                </button>
            </div>

            {/* 导航 */}
            <nav className="flex-1 px-2 py-3 space-y-0.5">
                {navItems.map(({ href, label, shortcut, Icon }) => {
                    const active = isActive(href);
                    const badge  = href === "/favorites" && favorites.length > 0 ? favorites.length : 0;
                    return (
                        <Link key={href} href={href} title={collapsed ? `${label}${shortcut ? "  " + shortcut : ""}` : undefined}
                            className={`flex items-center gap-2.5 rounded-lg text-sm
                                        transition-colors group
                                        ${collapsed ? "justify-center px-0 py-2.5" : "px-3 py-2"}
                                        ${active
                                            ? "bg-indigo-600 text-white"
                                            : "text-gray-400 hover:text-white hover:bg-gray-800"}`}>
                            <div className="relative flex-shrink-0">
                                <Icon size={15} />
                                {badge > 0 && collapsed && (
                                    <span className="absolute -top-1 -right-1 w-3.5 h-3.5 bg-amber-500 rounded-full
                                                     flex items-center justify-center text-[8px] text-white font-bold">
                                        {badge > 9 ? "9+" : badge}
                                    </span>
                                )}
                            </div>
                            {!collapsed && (
                                <>
                                    <span className="flex-1">{label}</span>
                                    {badge > 0 && (
                                        <span className="px-1.5 py-0.5 bg-amber-500/20 text-amber-400
                                                         text-[10px] font-bold rounded-full">
                                            {badge}
                                        </span>
                                    )}
                                    {shortcut && badge === 0 && (
                                        <span className={`text-xs font-mono ${active ? "text-indigo-200" : "text-gray-600"}`}>
                                            {shortcut}
                                        </span>
                                    )}
                                </>
                            )}
                        </Link>
                    );
                })}
            </nav>

            {/* 快捷键提示（展开时显示） */}
            {!collapsed && (
                <div className="px-4 py-2 border-t border-gray-800/50">
                    <div className="text-xs text-gray-700 space-y-0.5">
                        <div className="flex justify-between"><span>搜索</span><span className="font-mono">⌘K</span></div>
                        <div className="flex justify-between"><span>问答</span><span className="font-mono">⌘/</span></div>
                    </div>
                </div>
            )}

            {/* 底部用户 + 操作 */}
            <div className="border-t border-gray-800">
                {!collapsed && user && (
                    <div className="px-4 py-3 border-b border-gray-800">
                        <div className="text-xs text-white font-medium truncate">
                            {user.full_name || user.username}
                        </div>
                        <div className="text-xs text-gray-500 mt-0.5 truncate">{user.department}</div>
                    </div>
                )}
                <div className={`py-3 flex items-center gap-2
                                 ${collapsed ? "flex-col justify-center px-0" : "px-4 justify-between"}`}>
                    {!collapsed && <div className="text-xs text-gray-600">v1.0.0</div>}
                    <ThemeToggle />
                    <button onClick={handleLogout}
                        className="p-1.5 rounded-lg text-gray-400 hover:text-red-400
                                   hover:bg-gray-800 transition-colors"
                        title="退出登录">
                        <LogOut size={15} />
                    </button>
                </div>
            </div>
        </aside>
    );
}
