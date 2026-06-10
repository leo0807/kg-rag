"use client";

import Link from "next/link";
import { useState, useEffect, useCallback } from "react";
import { fetchApi } from "@/lib/api";
import { LegacyEvalPanel } from "./components/LegacyEvalPanel";

type EvalRun = {
  id: string; run_name: string; status: string;
  accuracy: number | null; avg_latency_ms: number | null;
  total_questions: number; completed_questions: number;
  tags: string[]; created_at: string; completed_at: string | null;
};

type Tab = "runs" | "classic";

const STATUS_COLOR: Record<string, string> = {
  completed: "text-green-400",
  running:   "text-blue-400",
  failed:    "text-red-400",
  cancelled: "text-gray-400",
  pending:   "text-yellow-400",
};

export default function AdminEvalPage() {
  const [tab, setTab] = useState<Tab>("runs");
  const [runs, setRuns] = useState<EvalRun[]>([]);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchApi<EvalRun[]>("/api/admin/eval/runs");
      setRuns(data ?? []);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { if (tab === "runs") load(); }, [tab, load]);

  return (
    <div className="flex-1 overflow-auto bg-gray-950 p-6 space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white">评测中心</h1>
          <p className="text-sm text-gray-400 mt-0.5">持久化评测运行 · 误差分析 · 策略对比</p>
        </div>
        <div className="flex gap-2">
          <Link href="/admin/eval/datasets"
            className="px-3 py-1.5 text-sm text-gray-300 border border-gray-700 rounded hover:bg-gray-800">
            数据集管理
          </Link>
          <Link href="/admin/eval/compare"
            className="px-3 py-1.5 text-sm text-gray-300 border border-gray-700 rounded hover:bg-gray-800">
            对比分析
          </Link>
          <Link href="/admin/eval/trends"
            className="px-3 py-1.5 text-sm text-gray-300 border border-gray-700 rounded hover:bg-gray-800">
            准确率趋势
          </Link>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-gray-800">
        {(["runs", "classic"] as Tab[]).map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm border-b-2 transition-colors ${
              tab === t ? "border-blue-500 text-white" : "border-transparent text-gray-400 hover:text-gray-200"
            }`}>
            {t === "runs" ? "持久化评测" : "经典评测"}
          </button>
        ))}
      </div>

      {tab === "classic" && <LegacyEvalPanel />}

      {tab === "runs" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-400">{runs.length} 条评测记录</span>
            <button onClick={load} disabled={loading}
              className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-500 disabled:opacity-50">
              {loading ? "加载中…" : "刷新"}
            </button>
          </div>

          {runs.length === 0 && !loading && (
            <div className="text-center py-16 text-gray-500">
              <p className="text-lg">暂无评测记录</p>
              <p className="text-sm mt-1">
                请先在
                <Link href="/admin/eval/datasets" className="text-blue-400 hover:underline mx-1">数据集管理</Link>
                中导入数据集，然后启动评测
              </p>
            </div>
          )}

          {runs.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-gray-400 border-b border-gray-800">
                    <th className="pb-2 pr-4 font-medium">运行名称</th>
                    <th className="pb-2 pr-4 font-medium">状态</th>
                    <th className="pb-2 pr-4 font-medium text-right">准确率</th>
                    <th className="pb-2 pr-4 font-medium text-right">平均延迟</th>
                    <th className="pb-2 pr-4 font-medium text-right">题目数</th>
                    <th className="pb-2 pr-4 font-medium">标签</th>
                    <th className="pb-2 font-medium">时间</th>
                    <th className="pb-2"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800/50">
                  {runs.map((r) => (
                    <tr key={r.id} className="text-gray-300 hover:bg-gray-900/50">
                      <td className="py-2.5 pr-4">
                        <Link href={`/admin/eval/runs/${r.id}`}
                          className="text-blue-400 hover:underline font-medium">
                          {r.run_name || r.id.slice(0, 8)}
                        </Link>
                      </td>
                      <td className={`py-2.5 pr-4 font-medium ${STATUS_COLOR[r.status] ?? "text-gray-400"}`}>
                        {r.status}
                      </td>
                      <td className="py-2.5 pr-4 text-right tabular-nums">
                        {r.accuracy != null ? `${(r.accuracy * 100).toFixed(1)}%` : "—"}
                      </td>
                      <td className="py-2.5 pr-4 text-right tabular-nums text-gray-400">
                        {r.avg_latency_ms != null ? `${r.avg_latency_ms.toFixed(0)}ms` : "—"}
                      </td>
                      <td className="py-2.5 pr-4 text-right tabular-nums">
                        {r.completed_questions}/{r.total_questions}
                      </td>
                      <td className="py-2.5 pr-4">
                        <div className="flex flex-wrap gap-1">
                          {(r.tags ?? []).map((tag) => (
                            <span key={tag} className="px-1.5 py-0.5 bg-gray-800 text-gray-300 text-xs rounded">
                              {tag}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="py-2.5 text-gray-500 text-xs whitespace-nowrap">
                        {new Date(r.created_at).toLocaleDateString("zh-CN")}
                      </td>
                      <td className="py-2.5 pl-2">
                        <Link href={`/admin/eval/runs/${r.id}`}
                          className="text-xs text-gray-500 hover:text-gray-300">
                          详情 →
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
