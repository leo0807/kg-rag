"use client";

import {
  CartesianGrid, Legend, Line, LineChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { fmtTokens } from "./ModelDistributionChart";

interface TrendItem { date: string; requests: number; tokens: number; cost_usd: number; avg_latency_ms?: number }

export function TrendLineChart({ trend }: { trend: TrendItem[] }) {
  if (trend.length === 0) {
    return <div className="h-64 flex items-center justify-center text-gray-500 text-sm">暂无数据</div>;
  }
  return (
    <ResponsiveContainer width="100%" height={240}>
      <LineChart data={trend} margin={{ left: 0, right: 8, top: 4, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
        <XAxis dataKey="date" tick={{ fill: "#6b7280", fontSize: 11 }}
          tickFormatter={(v: string) => v.slice(5)} />
        <YAxis tick={{ fill: "#6b7280", fontSize: 11 }}
          tickFormatter={(v: number) => fmtTokens(v)} width={52} />
        <YAxis yAxisId="right" orientation="right" tick={{ fill: "#6b7280", fontSize: 11 }} width={36} />
        <Tooltip
          contentStyle={{ background: "#1f2937", border: "1px solid #374151", borderRadius: 8 }}
          formatter={(v, name) => [
            name === "tokens" ? fmtTokens(Number(v)) : String(v),
            name === "tokens" ? "总 Token" : "请求数",
          ]}
          labelStyle={{ color: "#9ca3af", fontSize: 12 }}
        />
        <Legend formatter={(v) => v === "tokens" ? "Token 总量" : "请求数"}
          wrapperStyle={{ fontSize: 12, color: "#9ca3af" }} />
        <Line type="monotone" dataKey="tokens" stroke="#6366f1" strokeWidth={2}
          dot={{ fill: "#6366f1", r: 3 }} activeDot={{ r: 5 }} />
        <Line type="monotone" dataKey="requests" stroke="#10b981" strokeWidth={2}
          dot={{ fill: "#10b981", r: 3 }} activeDot={{ r: 5 }} yAxisId="right" />
      </LineChart>
    </ResponsiveContainer>
  );
}
