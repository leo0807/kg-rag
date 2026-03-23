"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const navItems = [
    { href: "/ingest", label: "导入文件" },
    { href: "/library", label: "文档库" },
    { href: "/query", label: "智能问答" },
    { href: "/graph", label: "图谱可视化" },
];

export default function Sidebar() {
    const pathname = usePathname();

    return (
        <aside className="w-48 shrink-0 bg-gray-900 border-r border-gray-800 flex flex-col">
            <div className="px-4 py-5 border-b border-r-gray-800">
                <div className="font-semibold text-white">CPS 知识库</div>
                <div className="text-xs text-gray-500 mt-1">航空工艺规范</div>
            </div>
            <nav className="flex-1 px-2 py-3">
                {navItems.map(({ href, label }) => {
                    const isActive = pathname.startsWith(href);
                    return (
                        (
                            <Link
                                key={href}
                                href={href}
                                className={`block px-3 py-2 rounded-md text-sm mb-1 ${isActive
                                    ? "bg-indigo-600 text-white"
                                    : "text-gray-400 hover:text-white hover:bg-gray-800"
                                    }`} >
                                {label}
                            </Link>
                        )
                    )
                })}
            </nav>
        </aside >
    );
}