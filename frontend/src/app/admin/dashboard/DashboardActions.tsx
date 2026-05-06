"use client";

import { ExternalLink, RefreshCw, Trash2, Zap } from "lucide-react";
import { useState } from "react";
import { getAuthHeaders } from "@/lib/api";
import type { DashboardData } from "./useDashboard";

const API = "http://localhost:8000";

function ActionItem({ label, href, type }: { label: string; href: string; type: string }) {
    return (
        <a href={href} className={`flex items-center gap-2 text-sm px-3 py-2 rounded-lg transition-colors ${
            type === "warning" ? "text-amber-300 bg-amber-950/30 hover:bg-amber-950/50"
            : "text-rose-300 bg-rose-950/30 hover:bg-rose-950/50"
        }`}>
            <span className="flex-1">{label}</span>
            <ExternalLink size={12} />
        </a>
    );
}

export function DashboardActions({ data, onRefresh }: { data: DashboardData; onRefresh: () => void }) {
    const [clearMsg, setClearMsg] = useState("");
    const [predictMsg, setPredictMsg] = useState("");

    async function clearCache() {
        setClearMsg("清理中…");
        try {
            const headers = await getAuthHeaders();
            await fetch(`${API}/api/admin/cache/flush`, { method: "POST", headers });
            setClearMsg("已清理");
        } catch { setClearMsg("失败"); }
        setTimeout(() => setClearMsg(""), 3000);
    }

    async function triggerPredict() {
        setPredictMsg("启动中…");
        try {
            const headers = await getAuthHeaders();
            await fetch(`${API}/api/admin/graph/predict`, { method: "POST", headers });
            setPredictMsg("已启动");
        } catch { setPredictMsg("失败"); }
        setTimeout(() => setPredictMsg(""), 3000);
    }

    return (
        <div className="grid md:grid-cols-2 gap-4">
            {/* Pending actions */}
            <div className="rounded-2xl border border-gray-800 bg-gray-900 p-4 space-y-3">
                <div className="text-sm font-medium text-gray-300">待处理事项</div>
                {data.actions.length === 0 ? (
                    <div className="text-xs text-gray-600 py-4 text-center">无待处理事项</div>
                ) : (
                    <div className="space-y-1.5">
                        {data.actions.map((a, i) => <ActionItem key={i} {...a} />)}
                    </div>
                )}

                <div className="pt-1 border-t border-gray-800 space-y-1.5">
                    <div className="text-xs text-gray-500 mb-1">快速操作</div>
                    <button type="button" onClick={clearCache}
                        className="flex w-full items-center gap-2 px-3 py-2 rounded-lg text-sm text-gray-300 bg-gray-800 hover:bg-gray-700 transition-colors">
                        <Trash2 size={13} />清理缓存{clearMsg && <span className="ml-auto text-xs text-gray-400">{clearMsg}</span>}
                    </button>
                    <button type="button" onClick={triggerPredict}
                        className="flex w-full items-center gap-2 px-3 py-2 rounded-lg text-sm text-gray-300 bg-gray-800 hover:bg-gray-700 transition-colors">
                        <Zap size={13} />运行关系预测{predictMsg && <span className="ml-auto text-xs text-gray-400">{predictMsg}</span>}
                    </button>
                    <button type="button" onClick={onRefresh}
                        className="flex w-full items-center gap-2 px-3 py-2 rounded-lg text-sm text-gray-300 bg-gray-800 hover:bg-gray-700 transition-colors">
                        <RefreshCw size={13} />立即刷新
                    </button>
                </div>
            </div>

            {/* Recent events */}
            <div className="rounded-2xl border border-gray-800 bg-gray-900 p-4 space-y-2">
                <div className="text-sm font-medium text-gray-300">近期操作日志</div>
                {data.recent_events.length === 0 ? (
                    <div className="text-xs text-gray-600 py-4 text-center">暂无记录</div>
                ) : (
                    <div className="space-y-1.5 overflow-auto max-h-48">
                        {data.recent_events.map((ev, i) => (
                            <div key={i} className="flex items-start gap-2 text-xs">
                                <span className="shrink-0 mt-0.5 w-1.5 h-1.5 rounded-full bg-indigo-500" />
                                <div className="flex-1 min-w-0">
                                    <span className="text-gray-300">{ev.action}</span>
                                    {ev.resource && <span className="text-gray-500"> · {ev.resource}</span>}
                                </div>
                                <span className="shrink-0 text-gray-600">{ev.username}</span>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}
