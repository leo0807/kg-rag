"use client";

import {
    LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
    PieChart, Pie, Cell, Legend,
} from "recharts";
import type { DashboardData } from "./useDashboard";

const SERVICE_LABELS: Record<string, string> = {
    neo4j: "Neo4j", milvus: "Milvus", elasticsearch: "ES",
};

const PIE_COLORS = ["#6366f1", "#f59e0b", "#10b981", "#ec4899", "#a78bfa"];

function fmtDate(d: string) {
    return d.slice(5); // "MM-DD"
}

export function DashboardCharts({ data }: { data: DashboardData }) {
    const nodeData = [
        { name: "节点", value: data.graph.node_count },
        { name: "孤立", value: data.graph.orphan_count },
        { name: "关系", value: data.graph.rel_count },
    ].filter(d => d.value > 0);

    return (
        <div className="grid md:grid-cols-2 gap-4">
            {/* 7-day query trend */}
            <div className="rounded-2xl border border-gray-800 bg-gray-900 p-4">
                <div className="text-sm font-medium text-gray-300 mb-3">7日查询趋势</div>
                {data.trend.length === 0 ? (
                    <div className="h-32 flex items-center justify-center text-xs text-gray-600">暂无数据</div>
                ) : (
                    <ResponsiveContainer width="100%" height={140}>
                        <LineChart data={data.trend} margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                            <XAxis dataKey="date" tickFormatter={fmtDate} tick={{ fontSize: 10, fill: "#6b7280" }} />
                            <YAxis tick={{ fontSize: 10, fill: "#6b7280" }} />
                            <Tooltip contentStyle={{ background: "#111827", border: "1px solid #374151", fontSize: 12 }}
                                formatter={(v: unknown) => [Number(v), "次"]} />
                            <Line type="monotone" dataKey="requests" stroke="#6366f1" strokeWidth={2} dot={false} />
                        </LineChart>
                    </ResponsiveContainer>
                )}
            </div>

            {/* Service health + graph pie */}
            <div className="rounded-2xl border border-gray-800 bg-gray-900 p-4 space-y-3">
                <div className="text-sm font-medium text-gray-300">服务状态</div>
                <div className="space-y-2">
                    {Object.entries(data.services).map(([key, svc]) => (
                        <div key={key} className="flex items-center gap-2">
                            <span className={`w-2 h-2 rounded-full shrink-0 ${svc.is_ok ? "bg-emerald-400" : "bg-rose-500"}`} />
                            <span className="text-sm text-gray-300 flex-1">{SERVICE_LABELS[key] ?? key}</span>
                            {svc.latency_ms != null && (
                                <span className="text-xs text-gray-500">{svc.latency_ms}ms</span>
                            )}
                            {!svc.is_ok && <span className="text-xs text-rose-400 truncate max-w-32">{svc.error}</span>}
                        </div>
                    ))}
                </div>

                <div className="text-sm font-medium text-gray-300 pt-1">图谱分布</div>
                <ResponsiveContainer width="100%" height={100}>
                    <PieChart>
                        <Pie data={nodeData} cx="50%" cy="50%" outerRadius={40} dataKey="value" labelLine={false}>
                            {nodeData.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                        </Pie>
                        <Legend iconSize={8} wrapperStyle={{ fontSize: 11 }} />
                        <Tooltip contentStyle={{ background: "#111827", border: "1px solid #374151", fontSize: 12 }} />
                    </PieChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
}
