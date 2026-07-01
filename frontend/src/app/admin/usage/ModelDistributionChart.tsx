"use client";

import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

export const PIE_COLORS = ["#6366f1", "#f59e0b", "#10b981", "#ef4444", "#8b5cf6", "#06b6d4"];

export function fmtTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000)     return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

export function shortModel(m: string): string {
  return m.split("/").pop()?.replace(/[-_]instruct$/i, "") ?? m;
}

function PieLabel({ cx, cy, midAngle, innerRadius, outerRadius, percent }: {
  cx: number; cy: number; midAngle: number;
  innerRadius: number; outerRadius: number; percent: number;
}) {
  if (percent < 0.05) return null;
  const R = Math.PI / 180;
  const r = innerRadius + (outerRadius - innerRadius) * 0.55;
  const x = cx + r * Math.cos(-midAngle * R);
  const y = cy + r * Math.sin(-midAngle * R);
  return (
    <text x={x} y={y} fill="white" textAnchor="middle" dominantBaseline="central" fontSize={11}>
      {`${(percent * 100).toFixed(0)}%`}
    </text>
  );
}

interface PieItem { name: string; value: number; tokens: number }

export function ModelDistributionChart({ data }: { data: PieItem[] }) {
  if (data.length === 0) {
    return <div className="h-64 flex items-center justify-center text-gray-500 text-sm">暂无数据</div>;
  }
  return (
    <div className="flex items-center gap-4">
      <ResponsiveContainer width="60%" height={240}>
        <PieChart>
          <Pie data={data} dataKey="value" nameKey="name" cx="50%" cy="50%"
            outerRadius={100} innerRadius={48} labelLine={false} label={PieLabel as never}>
            {data.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
          </Pie>
          <Tooltip
            contentStyle={{ background: "#1f2937", border: "1px solid #374151", borderRadius: 8 }}
            formatter={(v) => [`${v} 次`]}
          />
        </PieChart>
      </ResponsiveContainer>
      <div className="flex-1 space-y-2 text-sm">
        {data.map((item, i) => (
          <div key={item.name} className="flex items-center gap-2">
            <span className="inline-block w-3 h-3 rounded-full shrink-0"
              style={{ background: PIE_COLORS[i % PIE_COLORS.length] }} />
            <span className="text-gray-300 truncate" title={item.name}>{item.name}</span>
            <span className="text-gray-500 ml-auto shrink-0">{fmtTokens(item.tokens)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
