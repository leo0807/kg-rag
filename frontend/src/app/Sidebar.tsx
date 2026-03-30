"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import Link from "next/link";
import ThemeToggle from "@/components/ThemeToggle";
import { LogOut } from "lucide-react";

const navItems = [
    { href: "/ingest", label: "导入文件", shortcut: "" },
    { href: "/library", label: "文档库", shortcut: "" },
    { href: "/search", label: "全局搜索", shortcut: "⌘K" },
    { href: "/query", label: "智能问答", shortcut: "⌘/" },
    { href: "/graph", label: "图谱可视化", shortcut: "" },
    { href: "/compare", label: "文档对比", shortcut: "" },
    { href: "/settings", label: "设置", shortcut: "" },
];

interface UserInfo {
    username: string;
    full_name: string;
    department: string;
}

export default function Sidebar() {
    const pathname = usePathname();
    const router = useRouter();
    const [user, setUser] = useState<UserInfo | null>(null);

    useEffect(() => {
        const stored = localStorage.getItem("user");
        if (stored) {
            try { setUser(JSON.parse(stored)); } catch { }
        }

        // 全局键盘快捷键
        function handleKeyDown(e: KeyboardEvent) {
            const tag = (e.target as HTMLElement).tagName;
            if (["INPUT", "TEXTAREA", "SELECT"].includes(tag)) return;

            // ⌘K → 全局搜索
            if ((e.metaKey || e.ctrlKey) && e.key === "k") {
                e.preventDefault();
                router.push("/search");
            }
            // ⌘/ → 智能问答
            if ((e.metaKey || e.ctrlKey) && e.key === "/") {
                e.preventDefault();
                router.push("/query");
            }
            // ⌘B → 文档库
            if ((e.metaKey || e.ctrlKey) && e.key === "b") {
                e.preventDefault();
                router.push("/library");
            }
            // ⌘G → 图谱
            if ((e.metaKey || e.ctrlKey) && e.key === "g") {
                e.preventDefault();
                router.push("/graph");
            }
        }

        window.addEventListener("keydown", handleKeyDown);
        return () => window.removeEventListener("keydown", handleKeyDown);
    }, [router]);

    function isActive(href: string) {
        return pathname === href || pathname.startsWith(href + "/");
    }

    function handleLogout() {
        localStorage.removeItem("token");
        localStorage.removeItem("user");
        router.push("/login");
    }

    return (
        <aside className="w-44 flex-shrink-0 bg-gray-950 border-r border-gray-800
                      flex flex-col">
            {/* Logo */}
            <div className="px-4 py-5 border-b border-gray-800">
                <div className="text-base font-bold text-white">CPS 知识库</div>
                <div className="text-xs text-gray-500 mt-0.5">航空工艺规范</div>
            </div>

            {/* 导航 */}
            <nav className="flex-1 px-3 py-4 space-y-0.5">
                {navItems.map(item => (
                    <Link key={item.href} href={item.href}
                        className={`flex items-center justify-between px-3 py-2 rounded-lg text-sm
                        transition-colors ${isActive(item.href)
                                ? "bg-indigo-600 text-white"
                                : "text-gray-400 hover:text-white hover:bg-gray-800"
                            }`}>
                        <span>{item.label}</span>
                        {item.shortcut && (
                            <span className={`text-xs font-mono ${isActive(item.href) ? "text-indigo-200" : "text-gray-600"
                                }`}>
                                {item.shortcut}
                            </span>
                        )}
                    </Link>
                ))}
            </nav>

            {/* 快捷键提示 */}
            <div className="px-4 py-2 border-t border-gray-800/50">
                <div className="text-xs text-gray-700 space-y-0.5">
                    <div className="flex justify-between"><span>搜索</span><span className="font-mono">⌘K</span></div>
                    <div className="flex justify-between"><span>问答</span><span className="font-mono">⌘/</span></div>
                    <div className="flex justify-between"><span>文档库</span><span className="font-mono">⌘B</span></div>
                    <div className="flex justify-between"><span>图谱</span><span className="font-mono">⌘G</span></div>
                </div>
            </div>

            {/* 底部用户信息 */}
            <div className="border-t border-gray-800">
                {user && (
                    <div className="px-4 py-3 border-b border-gray-800">
                        <div className="text-xs text-white font-medium">
                            {user.full_name || user.username}
                        </div>
                        <div className="text-xs text-gray-500 mt-0.5">{user.department}</div>
                    </div>
                )}
                <div className="px-4 py-3 flex items-center justify-between">
                    <div className="text-xs text-gray-600">v1.0.0</div>
                    <div className="flex items-center gap-2">
                        <ThemeToggle />
                        <button onClick={handleLogout}
                            className="p-1.5 rounded-lg text-gray-400 hover:text-red-400
                         hover:bg-gray-800 transition-colors"
                            title="退出登录">
                            <LogOut size={16} />
                        </button>
                    </div>
                </div>
            </div>
        </aside>
    );
}