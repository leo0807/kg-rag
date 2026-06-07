"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import Sidebar from "./Sidebar";
import ErrorBoundary from "@/components/ErrorBoundary";
import ShortcutsModal from "@/components/ShortcutsModal";
import { useGlobalKeyboard } from "@/hooks/useKeyboard";
import { LogOut, Menu, X } from "lucide-react";

const NO_SIDEBAR_PATHS = ["/login"];

export default function ConditionalLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    const pathname = usePathname();
    const router = useRouter();
    const showSidebar = !NO_SIDEBAR_PATHS.includes(pathname);
    const [mobileOpen, setMobileOpen] = useState(false);

    const { showShortcuts, setShowShortcuts } = useGlobalKeyboard();

    function handleMobileLogout() {
        localStorage.removeItem("token");
        localStorage.removeItem("user");
        router.push("/login");
    }

    useEffect(() => {
        if (!showSidebar) return;
        const token = localStorage.getItem("token");
        if (!token) router.push("/login");
    }, [pathname, showSidebar, router]);

    // 全局 401 拦截：仅拦截 /api/ 请求，避免干扰 Next.js 内部请求（HMR/RSC/路由）
    // 注意：外层使用普通函数（非 async），确保非 API 请求返回原始 Promise，
    // 不引入额外的微任务延迟，避免破坏 Turbopack 路由参数初始化时序。
    useEffect(() => {
        const original = window.fetch;
        window.fetch = function (...args: Parameters<typeof fetch>): Promise<Response> {
            const url = typeof args[0] === "string" ? args[0]
                : args[0] instanceof Request ? args[0].url : "";
            // 非 API 请求：直接返回原始 Promise，零额外开销
            if (!url.includes("/api/")) {
                return original.apply(window, args);
            }
            // API 请求：检查 401 并跳转登录
            return original.apply(window, args).then(res => {
                if (res.status === 401
                    && !url.includes("/api/auth/login")
                    && !url.includes("/api/auth/refresh")
                    && !url.includes("/api/pipeline/")) {
                    localStorage.removeItem("token");
                    localStorage.removeItem("user");
                    window.location.href = "/login";
                }
                return res;
            });
        };
        return () => { window.fetch = original; };
    }, []);

    // 路由切换时关闭移动端菜单
    useEffect(() => { setMobileOpen(false); }, [pathname]);

    if (!showSidebar) {
        return (
            <div className="min-h-screen bg-gray-950">
                <ShortcutsModal
                    open={showShortcuts}
                    onClose={() => setShowShortcuts(false)}
                />
                {children}
            </div>
        );
    }

    return (
        <div className="flex h-screen bg-gray-950 overflow-hidden">
            <ShortcutsModal open={showShortcuts} onClose={() => setShowShortcuts(false)} />
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
            <div className={`fixed inset-y-0 left-0 z-50 md:hidden transition-transform duration-200 ${mobileOpen ? "translate-x-0" : "-translate-x-full"
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
                    <span className="text-sm font-medium text-white">商飞大模型</span>
                    <button
                        onClick={handleMobileLogout}
                        className="ml-auto p-1.5 rounded-lg text-gray-400 hover:text-red-400 hover:bg-gray-800 transition-colors"
                        aria-label="退出登录"
                    >
                        <LogOut size={18} />
                    </button>
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
