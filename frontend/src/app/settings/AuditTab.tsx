"use client";

import { useState, useEffect } from "react";
import { AuditRow, getToken } from "./types";

export function AuditTab() {
    const [auditLogs, setAuditLogs] = useState<AuditRow[]>([]);
    const [auditTotal, setAuditTotal] = useState(0);
    const [auditPage, setAuditPage] = useState(1);

    useEffect(() => { loadPage(1); }, []);

    async function loadPage(page: number) {
        const res = await fetch(`/api/users/audit-logs?page=${page}&per_page=15`, {
            headers: { Authorization: `Bearer ${getToken()}` },
        });
        if (!res.ok) return;
        const data = await res.json();
        setAuditLogs(data.data ?? []);
        setAuditTotal(data.total ?? 0);
        setAuditPage(page);
    }

    return (
        <div>
            <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden mb-4">
                <table className="w-full text-sm">
                    <thead>
                        <tr className="border-b border-gray-800 text-gray-400 text-left">
                            <th className="px-4 py-3">时间</th>
                            <th className="px-4 py-3">用户</th>
                            <th className="px-4 py-3">操作</th>
                            <th className="px-4 py-3">详情</th>
                        </tr>
                    </thead>
                    <tbody>
                        {auditLogs.map(log => (
                            <tr key={log.id} className="border-b border-gray-800/50">
                                <td className="px-4 py-2.5 text-xs text-gray-500 whitespace-nowrap">
                                    {new Date(log.created_at).toLocaleString("zh-CN")}
                                </td>
                                <td className="px-4 py-2.5 text-xs text-gray-300">
                                    {log.full_name || log.username}
                                </td>
                                <td className="px-4 py-2.5">
                                    <span className={`px-2 py-0.5 rounded text-xs ${
                                        log.action === "login"             ? "bg-green-500/20 text-green-400"   :
                                        log.action === "register"          ? "bg-indigo-500/20 text-indigo-400" :
                                        log.action.includes("delete")      ? "bg-red-500/20 text-red-400"       :
                                                                             "bg-gray-700 text-gray-400"
                                    }`}>
                                        {log.action}
                                    </span>
                                </td>
                                <td className="px-4 py-2.5 text-xs text-gray-400">{log.detail}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
            <div className="flex items-center gap-2">
                <button onClick={() => loadPage(auditPage - 1)} disabled={auditPage === 1}
                    className="px-3 py-1.5 bg-gray-900 border border-gray-700 rounded text-xs text-gray-400 disabled:opacity-40">
                    上一页
                </button>
                <span className="text-xs text-gray-500">共 {auditTotal} 条</span>
                <button onClick={() => loadPage(auditPage + 1)} disabled={auditLogs.length < 15}
                    className="px-3 py-1.5 bg-gray-900 border border-gray-700 rounded text-xs text-gray-400 disabled:opacity-40">
                    下一页
                </button>
            </div>
        </div>
    );
}
