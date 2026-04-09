"use client";

import React from "react";
import { STRATEGY_LABEL, DauPoint } from "./types";

export function SummaryCard({ icon: Icon, label, value, sub }: {
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

export function StrategyBadge({ strategy }: { strategy: string }) {
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

export function DauChart({ data, maxQ }: { data: DauPoint[]; maxQ: number }) {
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
