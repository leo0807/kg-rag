"use client";

import {
  CartesianGrid, Line, LineChart, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";

interface TrendItem {
  date: string;
  requests: number;
  avg_latency_ms?: number;
}

interface Props {
  trend: TrendItem[];
}

function fmtMs(ms: number): string {
  if (ms >= 1000) return `${(ms / 1000).toFixed(1)}s`;
  return `${ms}ms`;
}

export function PerformanceTrendPanel({ trend }: Props) {
  const hasLatency = trend.some((t) => (t.avg_latency_ms ?? 0) > 0);
  if (!hasLatency || trend.length === 0) return null;

  const maxMs = Math.max(...trend.map((t) => t.avg_latency_ms ?? 0));

  // Determine bottleneck annotation
  const worst = trend.reduce(
    (a, b) => ((b.avg_latency_ms ?? 0) > (a.avg_latency_ms ?? 0) ? b : a),
    trend[0],
  );

  return (
    <section className="mt-6 rounded-xl border p-5"
             style={{ borderColor: "var(--border)", background: "var(--card-bg)" }}>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
            响应时间趋势（过去 7 天）
          </h2>
          <p className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>
            平均查询响应时间
          </p>
        </div>
        <div className="text-right">
          <div className="text-lg font-bold" style={{ color: "var(--text-primary)" }}>
            {fmtMs(Math.round(trend.reduce((s, t) => s + (t.avg_latency_ms ?? 0), 0) / trend.length))}
          </div>
          <div className="text-xs" style={{ color: "var(--text-muted)" }}>7天均值</div>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={160}>
        <LineChart data={trend} margin={{ left: 0, right: 8, top: 4, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
          <XAxis dataKey="date" tick={{ fontSize: 10, fill: "var(--text-muted)" }}
                 tickFormatter={(v) => v.slice(5)} />
          <YAxis tickFormatter={fmtMs} tick={{ fontSize: 10, fill: "var(--text-muted)" }}
                 domain={[0, Math.ceil(maxMs * 1.2)]} />
          <Tooltip
            contentStyle={{ background: "var(--card-bg)", border: "1px solid var(--border)", fontSize: 12 }}
            formatter={(v: unknown) => [fmtMs(Number(v ?? 0)), "平均响应"]}
          />
          <Line type="monotone" dataKey="avg_latency_ms" name="平均响应"
                stroke="#f59e0b" strokeWidth={2} dot={{ r: 3 }} />
        </LineChart>
      </ResponsiveContainer>

      {worst && (
        <div className="mt-3 text-xs px-3 py-2 rounded-lg"
             style={{ background: "rgba(245,158,11,0.08)", color: "#d97706" }}>
          ⚠️ 峰值响应时间 {fmtMs(worst.avg_latency_ms ?? 0)} 出现在 {worst.date}，
          建议检查该日查询负载或模型配置
        </div>
      )}
    </section>
  );
}
