"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import Link from "next/link";
import ThemeToggle from "@/components/ThemeToggle";
import { LogOut } from "lucide-react";

const navItems = [
    { href: "/ingest", label: "导入文件" },
    { href: "/library", label: "文档库" },
    { href: "/query", label: "智能问答" },
    { href: "/graph", label: "图谱可视化" },
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
    }, []);

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
            <nav className="flex-1 px-3 py-4">
                {navItems.map(({ href, label }) => {
                    const isActive = pathname === href || pathname.startsWith(href + "/");
                    return (
                        <Link
                            key={href}
                            href={href}
                            className={`block px-3 py-2 rounded-md text-sm mb-1 ${isActive
                                    ? "bg-indigo-600 text-white"
                                    : "text-gray-400 hover:text-white hover:bg-gray-800"
                                }`}
                        >
                            {label}
                        </Link>
                    );
                })}
            </nav>

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
                        <button
                            onClick={handleLogout}
                            className="p-1.5 rounded-lg text-gray-400 hover:text-red-400
                         hover:bg-gray-800 transition-colors"
                            title="退出登录"
                        >
                            <LogOut size={16} />
                        </button>
                    </div>
                </div>
            </div>
        </aside>
    );
}