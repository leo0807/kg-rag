"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Download, RefreshCw, Users, MessageSquare, BarChart2, TrendingUp } from "lucide-react";
import { fetchApi } from "../../../lib/api";

const API = "http://localhost:8000";

const STRATEGY_LABEL: Record<string, string> = {
    parallel:        "并行",
    sequential:      "串行",
    graph_augmented: "图增强",
    gnn:             "GNN",
    multi_hop:       "多跳",
    "—":             "—",
};

interface Summary {
    total_active_users:     number;
    total_queries:          number;
    total_conversations:    number;
    avg_turns_per_session:  number | null;
    avg_daily_active_users: number;
}

interface UserRow {
    user_id:               string;
    username:              string;
    full_name:             string;
    department:            string;
    active_days:           number;
    total_queries:         number;
    weekly_queries:        number;
    total_conversations:   number;
    avg_turns_per_session: number | null;
    top_strategy:          string;
    last_active:           string | null;
}

interface DeptRow {
    department:            string;
    user_count:            number;
    avg_active_days:       number;
    total_queries:         number;
    weekly_queries:        number;
    total_conversations:   number;
    avg_turns_per_session: number | null;
    top_strategy:          string;
}

interface DauPoint { date: string; active_users: number; queries: number; }

interface Report {
    period:        { days: number; since: string; until: string };
    summary:       Summary;
    by_user:       UserRow[];
    by_department: DeptRow[];
    dau:           DauPoint[];
}

type Tab = "user" | "dept" | "dau";

function SummaryCard({ icon: Icon, label, value, sub }: {
    icon: React.ElementType; label: string; value: string | number; sub?: string;
}) {
    return (
        <div className="bg-gray-900 border border-gray-800 rounded-xl px-5 py-4 flex items-start gap-4">
            <div className="p-2.5 bg-indigo-900/40 rounded-lg shrink-0">
                <Icon size={18} className="text-indigo-400" />
            </div>
            <div>
                <div className="text-2xl font-semibold text-white leading-tight">{value}</div>
                <div className="text-xs text-gray-400 mt-0.5">{label}</div>
                {sub && <div className="text-xs text-gray-600 mt-0.5">{sub}</div>}
            </div>
        </div>
    );
}

function StrategyBadge({ strategy }: { strategy: string }) {
    const colors: Record<string, string> = {
        parallel:        "bg-indigo-900/50 text-indigo-300",
        sequential:      "bg-blue-900/50 text-blue-300",
        graph_augmented: "bg-emerald-900/50 text-emerald-300",
        gnn:             "bg-purple-900/50 text-purple-300",
        multi_hop:       "bg-amber-900/50 text-amber-300",
    };
    return (
        <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${colors[strategy] ?? "text-gray-500"}`}>
            {STRATEGY_LABEL[strategy] ?? strategy}
        </span>
    );
}

function DauChart({ data, maxQ }: { data: DauPoint[]; maxQ: number }) {
    if (!data.length) return <div className="text-xs text-gray-600 py-8 text-center">暂无数据</div>;
    return (
        <div className="flex items-end gap-1 h-32 overflow-x-auto pb-1">
            {data.map(d => {
                const pct = maxQ > 0 ? Math.round((d.queries / maxQ) * 100) : 0;
                return (
                    <div key={d.date} className="flex flex-col items-center gap-1 shrink-0" style={{ minWidth: 28 }}>
                        <div className="text-xs text-gray-500">{d.queries}</div>
                        <div
                            className="w-5 bg-indigo-600 rounded-sm transition-all"
                            style={{ height: `${Math.max(pct, 2)}%` }}
                            title={`${d.date}\n查询: ${d.queries}\nDAU: ${d.active_users}`}
                        />
                        <div
                            className="w-5 bg-emerald-700 rounded-sm"
                            style={{ height: `${Math.max(Math.round((d.active_users / Math.max(maxQ, 1)) * 100), 2)}%` }}
                        />
                        <div className="text-xs text-gray-600 rotate-45 origin-left" style={{ fontSize: 9 }}>
                            {d.date.slice(5)}
                        </div>
                    </div>
                );
            })}
        </div>
    );
}

export default function AnalyticsPage() {
    const [report,  setReport]  = useState<Report | null>(null);
    const [loading, setLoading] = useState(false);
    const [days,    setDays]    = useState(30);
    const [tab,     setTab]     = useState<Tab>("user");
    const [sortKey, setSortKey] = useState<string>("total_queries");
    const [sortAsc, setSortAsc] = useState(false);

    const load = useCallback(async (d: number) => {
        setLoading(true);
        try {
            const data = await fetchApi<Report>(`${API}/api/admin/analytics/user-activity?days=${d}`);
            setReport(data);
        } catch (e) {
            console.error(e);
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
        a.href      = token ? `${url}&token=${encodeURIComponent(token)}` : url;
        // Use fetch for proper auth header
        fetch(url, { headers: { Authorization: `Bearer ${token}` } })
            .then(r => r.blob())
            .then(blob => {
                const burl = URL.createObjectURL(blob);
                a.href     = burl;
                a.download = `user_activity_d${days}.csv`;
                a.click();
                URL.revokeObjectURL(burl);
            });
    }

    const SortTh = ({ col, label, right }: { col: string; label: string; right?: boolean }) => (
        <th
            className={`px-3 py-2.5 text-xs font-medium text-gray-400 cursor-pointer hover:text-white whitespace-nowrap select-none ${right ? "text-right" : "text-left"}`}
            onClick={() => handleSort(col)}
        >
            {label}
            {sortKey === col && <span className="ml-1 text-indigo-400">{sortAsc ? "↑" : "↓"}</span>}
        </th>
    );

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
                    {/* Days selector */}
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
                    <SummaryCard
                        icon={Users}
                        label="活跃用户数"
                        value={report.summary.total_active_users}
                        sub={`DAU 均值 ${report.summary.avg_daily_active_users}`}
                    />
                    <SummaryCard
                        icon={MessageSquare}
                        label="总查询次数"
                        value={report.summary.total_queries.toLocaleString()}
                        sub={`${days} 天内`}
                    />
                    <SummaryCard
                        icon={BarChart2}
                        label="总对话数"
                        value={report.summary.total_conversations.toLocaleString()}
                    />
                    <SummaryCard
                        icon={TrendingUp}
                        label="平均会话轮数"
                        value={report.summary.avg_turns_per_session ?? "—"}
                        sub="总查询 / 总对话"
                    />
                </div>
            )}

            {/* Tab bar */}
            <div className="flex items-center gap-1 border-b border-gray-800">
                {(["user", "dept", "dau"] as Tab[]).map(t => {
                    const labels = { user: "按用户", dept: "按部门", dau: "日活趋势" };
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

            {/* ── 按用户 ─────────────────────────────────────────────────── */}
            {!loading && report && tab === "user" && (
                <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                        <thead className="bg-gray-900 sticky top-0 z-10">
                            <tr>
                                <SortTh col="username"              label="工号" />
                                <SortTh col="full_name"             label="姓名" />
                                <SortTh col="department"            label="部门" />
                                <SortTh col="active_days"           label="活跃天数" right />
                                <SortTh col="total_queries"         label="总查询" right />
                                <SortTh col="weekly_queries"        label="周均查询" right />
                                <SortTh col="total_conversations"   label="对话数" right />
                                <SortTh col="avg_turns_per_session" label="均轮数" right />
                                <SortTh col="top_strategy"          label="主用策略" />
                                <SortTh col="last_active"           label="最近活跃" />
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-800">
                            {sorted(report.by_user).map(row => (
                                <tr key={row.user_id} className="hover:bg-gray-900/50 transition-colors">
                                    <td className="px-3 py-2.5 font-mono text-xs text-gray-300">{row.username}</td>
                                    <td className="px-3 py-2.5 text-gray-200">{row.full_name || "—"}</td>
                                    <td className="px-3 py-2.5 text-gray-400 text-xs">{row.department || "—"}</td>
                                    <td className="px-3 py-2.5 text-right text-gray-300">{row.active_days}</td>
                                    <td className="px-3 py-2.5 text-right font-semibold text-white">{row.total_queries.toLocaleString()}</td>
                                    <td className="px-3 py-2.5 text-right text-gray-400">{row.weekly_queries}</td>
                                    <td className="px-3 py-2.5 text-right text-gray-300">{row.total_conversations}</td>
                                    <td className="px-3 py-2.5 text-right text-gray-400">{row.avg_turns_per_session ?? "—"}</td>
                                    <td className="px-3 py-2.5"><StrategyBadge strategy={row.top_strategy} /></td>
                                    <td className="px-3 py-2.5 text-xs text-gray-600 font-mono whitespace-nowrap">
                                        {row.last_active ? row.last_active.slice(0, 10) : "—"}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                    {report.by_user.length === 0 && (
                        <div className="text-center py-12 text-gray-600 text-sm">暂无活跃用户数据</div>
                    )}
                </div>
            )}

            {/* ── 按部门 ─────────────────────────────────────────────────── */}
            {!loading && report && tab === "dept" && (
                <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                        <thead className="bg-gray-900 sticky top-0 z-10">
                            <tr>
                                <SortTh col="department"            label="部门" />
                                <SortTh col="user_count"            label="活跃人数" right />
                                <SortTh col="avg_active_days"       label="人均活跃天" right />
                                <SortTh col="total_queries"         label="总查询" right />
                                <SortTh col="weekly_queries"        label="周均查询" right />
                                <SortTh col="total_conversations"   label="对话数" right />
                                <SortTh col="avg_turns_per_session" label="均轮数" right />
                                <SortTh col="top_strategy"          label="主用策略" />
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-800">
                            {sorted(report.by_department).map(row => (
                                <tr key={row.department} className="hover:bg-gray-900/50 transition-colors">
                                    <td className="px-3 py-2.5 font-medium text-gray-200">{row.department}</td>
                                    <td className="px-3 py-2.5 text-right text-gray-300">{row.user_count}</td>
                                    <td className="px-3 py-2.5 text-right text-gray-400">{row.avg_active_days}</td>
                                    <td className="px-3 py-2.5 text-right font-semibold text-white">{row.total_queries.toLocaleString()}</td>
                                    <td className="px-3 py-2.5 text-right text-gray-400">{row.weekly_queries}</td>
                                    <td className="px-3 py-2.5 text-right text-gray-300">{row.total_conversations}</td>
                                    <td className="px-3 py-2.5 text-right text-gray-400">{row.avg_turns_per_session ?? "—"}</td>
                                    <td className="px-3 py-2.5"><StrategyBadge strategy={row.top_strategy} /></td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                    {report.by_department.length === 0 && (
                        <div className="text-center py-12 text-gray-600 text-sm">暂无部门数据</div>
                    )}
                </div>
            )}

            {/* ── 日活趋势 ───────────────────────────────────────────────── */}
            {!loading && report && tab === "dau" && (
                <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
                    <div className="flex items-center justify-between mb-4">
                        <div className="text-sm font-medium text-gray-300">每日活跃用户 & 查询量</div>
                        <div className="flex items-center gap-4 text-xs text-gray-500">
                            <span className="flex items-center gap-1.5">
                                <span className="w-3 h-3 rounded-sm bg-indigo-600 inline-block" />查询数
                            </span>
                            <span className="flex items-center gap-1.5">
                                <span className="w-3 h-3 rounded-sm bg-emerald-700 inline-block" />活跃用户
                            </span>
                        </div>
                    </div>
                    <DauChart data={report.dau} maxQ={maxQ} />
                    <div className="mt-4 overflow-x-auto">
                        <table className="w-full text-xs">
                            <thead>
                                <tr className="text-gray-500">
                                    <th className="text-left px-2 py-1">日期</th>
                                    <th className="text-right px-2 py-1">活跃用户</th>
                                    <th className="text-right px-2 py-1">查询次数</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-800">
                                {[...report.dau].reverse().map(d => (
                                    <tr key={d.date} className="hover:bg-gray-800/50">
                                        <td className="px-2 py-1.5 font-mono text-gray-400">{d.date}</td>
                                        <td className="px-2 py-1.5 text-right text-gray-300">{d.active_users}</td>
                                        <td className="px-2 py-1.5 text-right text-white font-medium">{d.queries}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                        {report.dau.length === 0 && (
                            <div className="text-center py-8 text-gray-600">暂无数据</div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}
