"use client";

import { useState, useEffect, useCallback } from "react";
import { Download, RefreshCw, Users, MessageSquare, BarChart2, TrendingUp } from "lucide-react";
import { fetchApi } from "../../../lib/api";
import { Report, StrategyStats, Tab } from "./types";
import { SummaryCard } from "./components";
import { StrategyTab } from "./StrategyTab";
import { UserTable } from "./UserTable";
import { DeptTable } from "./DeptTable";
import { DauView } from "./DauView";

const API = "http://localhost:8000";

export default function AnalyticsPage() {
    const [report,        setReport]        = useState<Report | null>(null);
    const [strategyStats, setStrategyStats] = useState<StrategyStats | null>(null);
    const [loading,       setLoading]       = useState(false);
    const [error,         setError]         = useState<string | null>(null);
    const [days,          setDays]          = useState(30);
    const [tab,           setTab]           = useState<Tab>("user");
    const [sortKey,       setSortKey]       = useState<string>("total_queries");
    const [sortAsc,       setSortAsc]       = useState(false);

    const load = useCallback(async (d: number) => {
        setLoading(true);
        setError(null);
        try {
            const [activity, strategy] = await Promise.all([
                fetchApi<Report>(`${API}/api/admin/analytics/user-activity?days=${d}`),
                fetchApi<StrategyStats>(`${API}/api/admin/analytics/strategy-stats?days=${d}`),
            ]);
            setReport(activity);
            setStrategyStats(strategy);
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : "加载失败，请检查后端服务是否正常");
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { load(days); }, [days, load]);

    function handleSort(key: string) {
        if (sortKey === key) setSortAsc(v => !v);
        else { setSortKey(key); setSortAsc(false); }
    }

    function sorted<T extends Record<string, any>>(rows: T[]): T[] {
        return [...rows].sort((a, b) => {
            const av = a[sortKey] ?? "";
            const bv = b[sortKey] ?? "";
            if (av === bv) return 0;
            const cmp = av < bv ? -1 : 1;
            return sortAsc ? cmp : -cmp;
        });
    }

    function exportCsv() {
        const token = localStorage.getItem("token");
        const url   = `${API}/api/admin/analytics/user-activity/csv?days=${days}`;
        const a     = document.createElement("a");
        fetch(url, { headers: { Authorization: `Bearer ${token}` } })
            .then(r => r.blob())
            .then(blob => {
                a.href     = URL.createObjectURL(blob);
                a.download = `user_activity_d${days}.csv`;
                a.click();
                URL.revokeObjectURL(a.href);
            });
    }

    const maxQ = report ? Math.max(...report.dau.map(d => d.queries), 1) : 1;

    return (
        <div className="flex-1 overflow-auto bg-gray-950 p-6 space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-xl font-semibold text-white">用户活跃度报表</h1>
                    <p className="text-xs text-gray-500 mt-0.5">
                        {report
                            ? `统计周期：${report.period.since.slice(0, 10)} ~ ${report.period.until.slice(0, 10)}`
                            : "加载中…"}
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    <div className="flex rounded-lg overflow-hidden border border-gray-700">
                        {[7, 14, 30, 90].map(d => (
                            <button
                                key={d}
                                onClick={() => setDays(d)}
                                className={`px-3 h-8 text-xs font-medium transition-colors ${
                                    days === d
                                        ? "bg-indigo-600 text-white"
                                        : "text-gray-400 hover:text-white hover:bg-gray-800"
                                }`}
                            >
                                {d}天
                            </button>
                        ))}
                    </div>
                    <button
                        onClick={() => load(days)}
                        className="p-2 rounded-lg bg-gray-800 text-gray-400 hover:text-white transition-colors"
                        title="刷新"
                    >
                        <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
                    </button>
                    <button
                        onClick={exportCsv}
                        disabled={!report}
                        className="flex items-center gap-1.5 px-3 h-8 rounded-lg bg-emerald-700 hover:bg-emerald-600
                                   text-white text-xs font-medium transition-colors disabled:opacity-40"
                    >
                        <Download size={13} />
                        导出 CSV
                    </button>
                </div>
            </div>

            {/* Summary cards */}
            {report && (
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                    <SummaryCard icon={Users}        label="活跃用户数"   value={report.summary.total_active_users}              sub={`DAU 均值 ${report.summary.avg_daily_active_users}`} />
                    <SummaryCard icon={MessageSquare} label="总查询次数"  value={report.summary.total_queries.toLocaleString()}  sub={`${days} 天内`} />
                    <SummaryCard icon={BarChart2}    label="总对话数"     value={report.summary.total_conversations.toLocaleString()} />
                    <SummaryCard icon={TrendingUp}   label="平均会话轮数" value={report.summary.avg_turns_per_session ?? "—"}    sub="总查询 / 总对话" />
                </div>
            )}

            {/* Tab bar */}
            <div className="flex items-center gap-1 border-b border-gray-800">
                {(["user", "dept", "dau", "strategy"] as Tab[]).map(t => {
                    const labels: Record<Tab, string> = { user: "按用户", dept: "按部门", dau: "日活趋势", strategy: "策略对比" };
                    return (
                        <button
                            key={t}
                            onClick={() => setTab(t)}
                            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors -mb-px ${
                                tab === t
                                    ? "border-indigo-500 text-white"
                                    : "border-transparent text-gray-500 hover:text-gray-300"
                            }`}
                        >
                            {labels[t]}
                        </button>
                    );
                })}
            </div>

            {loading && (
                <div className="flex items-center justify-center py-16 text-gray-500 text-sm">
                    <RefreshCw size={16} className="animate-spin mr-2" />加载中…
                </div>
            )}

            {!loading && error && (
                <div className="flex items-center gap-3 px-4 py-3 bg-red-950/40 border border-red-800/50
                                rounded-xl text-sm text-red-400">
                    <span className="shrink-0">⚠</span>
                    <span>{error}</span>
                    <button
                        onClick={() => load(days)}
                        className="ml-auto text-xs text-red-300 hover:text-white underline underline-offset-2"
                    >
                        重试
                    </button>
                </div>
            )}

            {!loading && report && tab === "user" && (
                <UserTable
                    rows={sorted(report.by_user)}
                    sortKey={sortKey} sortAsc={sortAsc} onSort={handleSort}
                />
            )}

            {!loading && report && tab === "dept" && (
                <DeptTable
                    rows={sorted(report.by_department)}
                    sortKey={sortKey} sortAsc={sortAsc} onSort={handleSort}
                />
            )}

            {tab === "strategy" && (
                <StrategyTab loading={loading} strategyStats={strategyStats} />
            )}

            {!loading && report && tab === "dau" && (
                <DauView dau={report.dau} maxQ={maxQ} />
            )}
        </div>
    );
}
