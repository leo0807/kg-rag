"use client";

import Link from "next/link";
import { useState, useEffect, useCallback } from "react";
import { fetchApi } from "@/lib/api";

type RunSummary = {
  id: string; run_name: string; status: string;
  accuracy: number | null; avg_latency_ms: number | null;
  total_questions: number; tags: string[]; created_at: string;
};

type Point = { date: string; accuracy: number; latency: number; name: string; id: string };

function MiniChart({ points, field }: { points: Point[]; field: "accuracy" | "latency" }) {
  if (points.length < 2) return null;
  const vals = points.map((p) => p[field]);
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  const range = max - min || 1;
  const W = 300; const H = 80; const PAD = 8;

  const xs = points.map((_, i) => PAD + (i / (points.length - 1)) * (W - PAD * 2));
  const ys = vals.map((v) => H - PAD - ((v - min) / range) * (H - PAD * 2));
  const path = xs.map((x, i) => `${i === 0 ? "M" : "L"}${x},${ys[i]}`).join(" ");

  return (
    <svg width={W} height={H} className="w-full">
      <polyline points={xs.map((x, i) => `${x},${ys[i]}`).join(" ")}
        fill="none" stroke="#3b82f6" strokeWidth={2} strokeLinejoin="round" />
      {xs.map((x, i) => (
        <circle key={i} cx={x} cy={ys[i]} r={3} fill="#3b82f6" />
      ))}
    </svg>
  );
}

export default function EvalTrendsPage() {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [strategyFilter, setStrategyFilter] = useState("all");

  const loadRuns = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchApi<RunSummary[]>("/api/admin/eval/runs");
      setRuns((data ?? []).filter((r) => r.status === "completed").reverse());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadRuns(); }, [loadRuns]);

  const strategies = Array.from(new Set(
    runs.flatMap((r) => r.tags.filter((t) => t.startsWith("strategy:")).map((t) => t.slice(9)))
  ));

  const getPoints = (strategy: string): Point[] =>
    runs
      .filter((r) => strategy === "all" || r.tags.includes(`strategy:${strategy}`))
      .filter((r) => r.accuracy != null)
      .map((r) => ({
        date: new Date(r.created_at).toLocaleDateString("zh-CN"),
        accuracy: Math.round((r.accuracy ?? 0) * 1000) / 10,
        latency: r.avg_latency_ms ?? 0,
        name: r.run_name || r.id.slice(0, 8),
        id: r.id,
      }));

  const points = getPoints(strategyFilter);

  const best = points.length > 0 ? points.reduce((a, b) => a.accuracy > b.accuracy ? a : b) : null;
  const latest = points[points.length - 1] ?? null;

  return (
    <div className="flex-1 overflow-auto bg-gray-950 p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href="/admin/eval" className="text-gray-400 hover:text-gray-200 text-sm">← 评测中心</Link>
          <h1 className="text-xl font-semibold text-white">准确率趋势</h1>
        </div>
        <select value={strategyFilter} onChange={(e) => setStrategyFilter(e.target.value)}
          className="bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-white">
          <option value="all">全部策略</option>
          {strategies.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      {loading && <p className="text-gray-400 text-sm">加载中…</p>}

      {!loading && runs.length === 0 && (
        <div className="text-center py-16 text-gray-500">暂无已完成的评测记录</div>
      )}

      {!loading && points.length > 0 && (
        <>
          {/* KPI cards */}
          <div className="grid grid-cols-3 gap-4">
            {[
              { label: "最高准确率", value: best ? `${best.accuracy.toFixed(1)}%` : "—", sub: best?.name ?? "" },
              { label: "最新准确率", value: latest ? `${latest.accuracy.toFixed(1)}%` : "—", sub: latest?.date ?? "" },
              { label: "评测次数", value: String(points.length), sub: `已筛选 / 共 ${runs.length}` },
            ].map((k) => (
              <div key={k.label} className="bg-gray-900 border border-gray-800 rounded-lg p-4">
                <p className="text-xs text-gray-500">{k.label}</p>
                <p className="text-2xl font-semibold text-white mt-1">{k.value}</p>
                <p className="text-xs text-gray-500 mt-0.5 truncate">{k.sub}</p>
              </div>
            ))}
          </div>

          {/* Chart */}
          {points.length >= 2 && (
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-5 space-y-3">
              <h2 className="text-sm font-medium text-gray-200">准确率走势（按时间排序）</h2>
              <MiniChart points={points} field="accuracy" />
              <div className="flex gap-2 flex-wrap">
                {points.map((p) => (
                  <Link key={p.id} href={`/admin/eval/runs/${p.id}`}
                    title={`${p.name}: ${p.accuracy}%`}
                    className="text-xs text-gray-500 hover:text-blue-400 whitespace-nowrap">
                    {p.date}: {p.accuracy}%
                  </Link>
                ))}
              </div>
            </div>
          )}

          {/* Table */}
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-gray-400 border-b border-gray-800">
                  <th className="pb-2 pr-4 font-medium">运行名称</th>
                  <th className="pb-2 pr-4 font-medium text-right">准确率</th>
                  <th className="pb-2 pr-4 font-medium text-right">平均延迟</th>
                  <th className="pb-2 pr-4 font-medium text-right">题目数</th>
                  <th className="pb-2 font-medium">日期</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800/50">
                {[...points].reverse().map((p) => (
                  <tr key={p.id} className="text-gray-300 hover:bg-gray-900/50">
                    <td className="py-2.5 pr-4">
                      <Link href={`/admin/eval/runs/${p.id}`} className="text-blue-400 hover:underline">
                        {p.name}
                      </Link>
                    </td>
                    <td className="py-2.5 pr-4 text-right tabular-nums">{p.accuracy.toFixed(1)}%</td>
                    <td className="py-2.5 pr-4 text-right tabular-nums text-gray-400">{p.latency.toFixed(0)}ms</td>
                    <td className="py-2.5 pr-4 text-right tabular-nums">
                      {runs.find((r) => r.id === p.id)?.total_questions ?? "—"}
                    </td>
                    <td className="py-2.5 text-gray-500">{p.date}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
