"use client";

import { Activity, RefreshCw } from "lucide-react";
import { useDashboard } from "./useDashboard";
import { DashboardKPIs } from "./DashboardKPIs";
import { DashboardCharts } from "./DashboardCharts";
import { DashboardActions } from "./DashboardActions";

function fmtTime(d: Date) {
    return d.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export default function DashboardPage() {
    const { data, loading, error, lastRefresh, refresh } = useDashboard();

    return (
        <div className="flex-1 overflow-auto bg-gray-950 p-6 space-y-6">
            {/* Header */}
            <div className="rounded-3xl border border-gray-800 bg-[radial-gradient(circle_at_top_left,rgba(99,102,241,0.15),transparent_40%),#111827] p-6">
                <div className="flex items-center justify-between gap-4">
                    <div>
                        <h1 className="text-2xl font-semibold text-white flex items-center gap-2">
                            <Activity size={22} className="text-indigo-400" />
                            系统综合健康看板
                        </h1>
                        <p className="mt-1 text-sm text-gray-400">每 30 秒自动刷新 · 聚合图谱、查询、存储与服务健康状态</p>
                    </div>
                    <div className="flex items-center gap-3 shrink-0">
                        {lastRefresh && (
                            <span className="text-xs text-gray-500">上次刷新 {fmtTime(lastRefresh)}</span>
                        )}
                        <button type="button" onClick={refresh}
                            className="inline-flex items-center gap-1.5 px-3 h-8 rounded-lg border border-gray-700 text-sm text-gray-300 hover:text-white hover:border-gray-500 transition-colors">
                            <RefreshCw size={13} />刷新
                        </button>
                    </div>
                </div>
            </div>

            {/* Error */}
            {error && (
                <div className="px-4 py-3 rounded-xl bg-red-950/40 border border-red-800/40 text-sm text-red-300">{error}</div>
            )}

            {/* Loading skeleton */}
            {loading && !data && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    {[...Array(4)].map((_, i) => (
                        <div key={i} className="h-24 rounded-2xl border border-gray-800 bg-gray-900 animate-pulse" />
                    ))}
                </div>
            )}

            {data && (
                <div className="space-y-4">
                    {/* Row 1: KPI cards + health ring */}
                    <DashboardKPIs data={data} />

                    {/* Row 2: trend chart + service status pie */}
                    <DashboardCharts data={data} />

                    {/* Row 3: pending actions + quick ops + recent events */}
                    <DashboardActions data={data} onRefresh={refresh} />
                </div>
            )}
        </div>
    );
}
