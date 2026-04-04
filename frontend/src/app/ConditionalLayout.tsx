"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import Sidebar from "./Sidebar";
import ErrorBoundary from "@/components/ErrorBoundary";
import { useGlobalKeyboard } from "@/hooks/useKeyboard";
import { Menu, X } from "lucide-react";

const NO_SIDEBAR_PATHS = ["/login"];

export default function ConditionalLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    const pathname    = usePathname();
    const router      = useRouter();
    const showSidebar = !NO_SIDEBAR_PATHS.includes(pathname);
    const [mobileOpen, setMobileOpen] = useState(false);

    useGlobalKeyboard();

    useEffect(() => {
        if (!showSidebar) return;
        const token = localStorage.getItem("token");
        if (!token) router.push("/login");
    }, [pathname, showSidebar, router]);

    // 全局 401 拦截：仅拦截 /api/ 请求，避免干扰 Next.js 内部请求（HMR/RSC/路由）
    useEffect(() => {
        const original = window.fetch;
        window.fetch = async function (...args: Parameters<typeof fetch>) {
            const url = typeof args[0] === "string" ? args[0]
                : args[0] instanceof Request ? args[0].url : "";
            // 只拦截业务 API 请求，内部 /_next/ 请求直接放行
            if (!url.includes("/api/")) {
                return original.apply(window, args);
            }
            const res = await original.apply(window, args);
            if (res.status === 401) {
                if (!url.includes("/api/auth/login") && !url.includes("/api/auth/refresh")) {
                    localStorage.removeItem("token");
                    localStorage.removeItem("user");
                    window.location.href = "/login";
                }
            }
            return res;
        };
        return () => { window.fetch = original; };
    }, []);

    // 路由切换时关闭移动端菜单
    useEffect(() => { setMobileOpen(false); }, [pathname]);

    if (!showSidebar) {
        return <div className="min-h-screen bg-gray-950">{children}</div>;
    }

    return (
        <div className="flex h-screen bg-gray-950 overflow-hidden">
            {/* 桌面端侧边栏 */}
            <div className="hidden md:flex shrink-0">
                <Sidebar />
            </div>

            {/* 移动端遮罩 */}
            {mobileOpen && (
                <div
                    className="fixed inset-0 z-40 bg-black/60 md:hidden"
                    onClick={() => setMobileOpen(false)}
                />
            )}

            {/* 移动端侧边栏（抽屉） */}
            <div className={`fixed inset-y-0 left-0 z-50 md:hidden transition-transform duration-200 ${
                mobileOpen ? "translate-x-0" : "-translate-x-full"
            }`}>
                <Sidebar />
            </div>

            {/* 主内容 */}
            <div className="flex-1 flex flex-col overflow-hidden min-w-0">
                {/* 移动端顶部导航栏 */}
                <div className="md:hidden flex items-center gap-3 px-4 py-3 border-b border-gray-800 bg-gray-950 shrink-0">
                    <button
                        onClick={() => setMobileOpen(v => !v)}
                        className="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-gray-800 transition-colors"
                        aria-label="打开菜单"
                    >
                        {mobileOpen ? <X size={18} /> : <Menu size={18} />}
                    </button>
                    <span className="text-sm font-medium text-white">CPS 知识库</span>
                </div>

                <main className="flex-1 overflow-auto">
                    <ErrorBoundary>
                        {children}
                    </ErrorBoundary>
                </main>
            </div>
        </div>
    );
}
