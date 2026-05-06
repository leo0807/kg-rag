"use client";

import { AlertTriangle, CheckCircle2, Cpu } from "lucide-react";
import type { DashboardData } from "./useDashboard";

function KPICard({ label, value, sub, warn }: { label: string; value: string; sub?: string; warn?: boolean }) {
    return (
        <div className={`rounded-2xl border p-4 space-y-1 ${warn ? "border-amber-700/50 bg-amber-950/20" : "border-gray-800 bg-gray-900"}`}>
            <div className="text-xs text-gray-500">{label}</div>
            <div className={`text-2xl font-bold ${warn ? "text-amber-300" : "text-white"}`}>{value}</div>
            {sub && <div className="text-xs text-gray-500">{sub}</div>}
        </div>
    );
}

function HealthRing({ score }: { score: number }) {
    const pct = Math.round(score * 100);
    const r = 28;
    const circ = 2 * Math.PI * r;
    const dash = (pct / 100) * circ;
    const color = pct >= 80 ? "#10b981" : pct >= 60 ? "#f59e0b" : "#ef4444";
    return (
        <div className="flex flex-col items-center justify-center gap-1">
            <svg width="80" height="80" viewBox="0 0 80 80">
                <circle cx="40" cy="40" r={r} fill="none" stroke="#374151" strokeWidth="7" />
                <circle cx="40" cy="40" r={r} fill="none" stroke={color} strokeWidth="7"
                    strokeDasharray={`${dash} ${circ - dash}`}
                    strokeLinecap="round" transform="rotate(-90 40 40)" />
                <text x="40" y="45" textAnchor="middle" fill={color} fontSize="16" fontWeight="700">{pct}%</text>
            </svg>
            <span className="text-xs text-gray-400">健康评分</span>
        </div>
    );
}

export function DashboardKPIs({ data }: { data: DashboardData }) {
    const warn = data.health_score < 0.8 || data.llm.avg_latency_ms > 5000;

    return (
        <div className="space-y-4">
            {warn && (
                <div className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-amber-950/40 border border-amber-700/40 text-sm text-amber-300">
                    <AlertTriangle size={15} />
                    {data.health_score < 0.8 && <span>图谱健康评分偏低（{Math.round(data.health_score * 100)}%）。</span>}
                    {data.llm.avg_latency_ms > 5000 && <span>LLM 平均响应超过 5s。</span>}
                </div>
            )}
            {!warn && (
                <div className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-emerald-950/30 border border-emerald-800/30 text-sm text-emerald-400">
                    <CheckCircle2 size={15} />系统运行正常
                </div>
            )}

            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="rounded-2xl border border-gray-800 bg-gray-900 p-4 flex items-center justify-center">
                    <HealthRing score={data.health_score} />
                </div>
                <KPICard label="图谱节点" value={data.graph.node_count.toLocaleString()} sub={`${data.graph.rel_count.toLocaleString()} 条关系`} />
                <KPICard label="7日查询次数" value={data.llm.queries_7d.toLocaleString()} sub={`均延迟 ${data.llm.avg_latency_ms}ms`} warn={data.llm.avg_latency_ms > 5000} />
                <KPICard label="冲突待处理" value={String(data.conflict_pending)} sub="点击前往仲裁" warn={data.conflict_pending > 0} />
            </div>

            {/* 内存使用卡片 */}
            {data.memory && data.memory.total_gb > 0 && (
                <div className="rounded-2xl border border-gray-800 bg-gray-900 p-4">
                    <div className="flex items-center gap-2 mb-3">
                        <Cpu size={14} className="text-indigo-400" />
                        <span className="text-xs font-medium text-white">内存使用</span>
                        <span className={`ml-auto text-xs font-bold ${data.memory.percent > 85 ? "text-red-400" : data.memory.percent > 70 ? "text-amber-400" : "text-emerald-400"}`}>
                            {data.memory.percent}%
                        </span>
                    </div>
                    <div className="w-full bg-gray-800 rounded-full h-2 mb-2">
                        <div
                            className={`h-2 rounded-full transition-all ${data.memory.percent > 85 ? "bg-red-500" : data.memory.percent > 70 ? "bg-amber-500" : "bg-emerald-500"}`}
                            style={{ width: `${Math.min(data.memory.percent, 100)}%` }}
                        />
                    </div>
                    <div className="flex justify-between text-[10px] text-gray-500 mb-2">
                        <span>已用 {data.memory.used_gb} GB</span>
                        <span>共 {data.memory.total_gb} GB</span>
                    </div>
                    {data.memory.models_loaded.length > 0 && (
                        <div className="mt-2 pt-2 border-t border-gray-800">
                            <div className="text-[10px] text-gray-500 mb-1">已加载模型</div>
                            <div className="flex flex-wrap gap-1">
                                {data.memory.models_loaded.map(m => (
                                    <span key={m.name} className="px-1.5 py-0.5 bg-indigo-950/50 border border-indigo-800/50 rounded text-[10px] text-indigo-300">
                                        {m.name}
                                    </span>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
