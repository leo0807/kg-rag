"use client";

import { useState, useEffect, useCallback } from "react";
import { fetchApi } from "@/lib/api";
import { ChevronLeft, ChevronRight } from "lucide-react";

interface AuditEntry {
    id: number;
    username: string;
    full_name: string;
    action: string;
    resource: string;
    detail: string;
    created_at: string;
}

interface AuditResponse {
    data: AuditEntry[];
    total: number;
    page: number;
    pages: number;
}

const ACTION_STYLE: Record<string, string> = {
    node_patch:   "bg-blue-500/15 text-blue-400 border border-blue-500/30",
    edge_create:  "bg-green-500/15 text-green-400 border border-green-500/30",
    edge_delete:  "bg-red-500/15 text-red-400 border border-red-500/30",
};

export default function AuditPage() {
    const [data, setData]   = useState<AuditEntry[]>([]);
    const [total, setTotal] = useState(0);
    const [pages, setPages] = useState(1);
    const [page, setPage]   = useState(1);
    const [loading, setLoading] = useState(false);

    const load = useCallback(async (p: number) => {
        setLoading(true);
        try {
            const res = await fetchApi<AuditResponse>(`/api/users/audit-logs?page=${p}&per_page=25`);
            setData(res.data); setTotal(res.total); setPages(res.pages); setPage(p);
        } finally { setLoading(false); }
    }, []);

    useEffect(() => { load(1); }, [load]);

    return (
        <div className="p-6 max-w-5xl mx-auto">
            <div className="flex items-center justify-between mb-6">
                <div>
                    <h1 className="text-xl font-semibold text-white">审计日志</h1>
                    <p className="text-xs text-gray-500 mt-0.5">共 {total} 条图谱编辑记录</p>
                </div>
            </div>

            {loading ? (
                <div className="text-gray-500 text-sm text-center py-12">加载中...</div>
            ) : (
                <div className="rounded-xl border border-gray-800 overflow-hidden">
                    <table className="w-full text-xs">
                        <thead className="bg-gray-900 border-b border-gray-800">
                            <tr className="text-left text-gray-500 uppercase tracking-wide">
                                <th className="px-4 py-2.5">时间</th>
                                <th className="px-4 py-2.5">操作人</th>
                                <th className="px-4 py-2.5">操作类型</th>
                                <th className="px-4 py-2.5">资源</th>
                                <th className="px-4 py-2.5 max-w-xs">详情</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-800/60">
                            {data.map(entry => (
                                <tr key={entry.id} className="hover:bg-gray-900/50">
                                    <td className="px-4 py-2.5 text-gray-500 font-mono whitespace-nowrap">
                                        {new Date(entry.created_at).toLocaleString("zh-CN")}
                                    </td>
                                    <td className="px-4 py-2.5 text-gray-300">
                                        {entry.full_name || entry.username}
                                        <span className="ml-1 text-gray-600">#{entry.username}</span>
                                    </td>
                                    <td className="px-4 py-2.5">
                                        <span className={`px-2 py-0.5 rounded-full text-[11px] font-medium ${ACTION_STYLE[entry.action] ?? "bg-gray-700 text-gray-400"}`}>
                                            {entry.action}
                                        </span>
                                    </td>
                                    <td className="px-4 py-2.5 text-indigo-400 font-mono max-w-[140px] truncate">{entry.resource}</td>
                                    <td className="px-4 py-2.5 text-gray-500 max-w-xs truncate">{entry.detail}</td>
                                </tr>
                            ))}
                            {data.length === 0 && (
                                <tr><td colSpan={5} className="px-4 py-8 text-center text-gray-600">暂无记录</td></tr>
                            )}
                        </tbody>
                    </table>
                </div>
            )}

            {pages > 1 && (
                <div className="flex items-center justify-center gap-3 mt-4">
                    <button onClick={() => load(page - 1)} disabled={page <= 1 || loading}
                        className="p-1.5 rounded bg-gray-800 text-gray-400 hover:text-white disabled:opacity-30">
                        <ChevronLeft size={14} />
                    </button>
                    <span className="text-xs text-gray-500">第 {page} / {pages} 页</span>
                    <button onClick={() => load(page + 1)} disabled={page >= pages || loading}
                        className="p-1.5 rounded bg-gray-800 text-gray-400 hover:text-white disabled:opacity-30">
                        <ChevronRight size={14} />
                    </button>
                </div>
            )}
        </div>
    );
}
