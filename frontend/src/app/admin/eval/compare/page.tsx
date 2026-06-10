"use client";

import Link from "next/link";
import { useState, useEffect, useCallback } from "react";
import { fetchApi } from "@/lib/api";

type RunSummary = {
  id: string; run_name: string; status: string;
  accuracy: number | null; avg_latency_ms: number | null;
  total_questions: number; created_at: string;
};

type CompareResult = {
  baseline: RunSummary;
  target: RunSummary;
  overall: { accuracy_change: string; latency_change_ms: number };
  changed_results: {
    wrong_to_right: string[];
    right_to_wrong: string[];
    still_wrong_different: string[];
  };
};

export default function EvalComparePage() {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [baselineId, setBaselineId] = useState("");
  const [targetId, setTargetId] = useState("");
  const [result, setResult] = useState<CompareResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [comparing, setComparing] = useState(false);
  const [error, setError] = useState("");

  const loadRuns = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchApi<RunSummary[]>("/api/admin/eval/runs");
      setRuns((data ?? []).filter((r) => r.status === "completed"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadRuns(); }, [loadRuns]);

  const handleCompare = async () => {
    if (!baselineId || !targetId) { setError("请选择两个评测运行"); return; }
    if (baselineId === targetId) { setError("请选择不同的评测运行"); return; }
    setComparing(true);
    setError("");
    setResult(null);
    try {
      const data = await fetchApi<CompareResult>("/api/admin/eval/runs/compare", {
        method: "POST",
        body: JSON.stringify({ baseline_id: baselineId, target_id: targetId }),
      });
      if (!data) { setError("对比失败"); return; }
      setResult(data);
    } finally {
      setComparing(false);
    }
  };

  const AccChange = ({ val }: { val: string }) => {
    const positive = val.startsWith("+");
    const negative = val.startsWith("-");
    return (
      <span className={`text-lg font-semibold ${positive ? "text-green-400" : negative ? "text-red-400" : "text-gray-300"}`}>
        {val}
      </span>
    );
  };

  return (
    <div className="flex-1 overflow-auto bg-gray-950 p-6 space-y-6">
      <div className="flex items-center gap-3">
        <Link href="/admin/eval" className="text-gray-400 hover:text-gray-200 text-sm">← 评测中心</Link>
        <h1 className="text-xl font-semibold text-white">运行对比</h1>
      </div>

      {/* Selection */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-5 space-y-4">
        <h2 className="text-sm font-medium text-gray-200">选择对比的运行</h2>
        {loading && <p className="text-gray-400 text-sm">加载运行列表…</p>}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-xs text-gray-400 block mb-1.5">基准运行（Baseline）</label>
            <select value={baselineId} onChange={(e) => setBaselineId(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-white">
              <option value="">请选择…</option>
              {runs.map((r) => (
                <option key={r.id} value={r.id} disabled={r.id === targetId}>
                  {r.run_name || r.id.slice(0, 8)} — {r.accuracy != null ? `${(r.accuracy * 100).toFixed(1)}%` : "—"}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-1.5">目标运行（Target）</label>
            <select value={targetId} onChange={(e) => setTargetId(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-white">
              <option value="">请选择…</option>
              {runs.map((r) => (
                <option key={r.id} value={r.id} disabled={r.id === baselineId}>
                  {r.run_name || r.id.slice(0, 8)} — {r.accuracy != null ? `${(r.accuracy * 100).toFixed(1)}%` : "—"}
                </option>
              ))}
            </select>
          </div>
        </div>
        {error && <p className="text-red-400 text-sm">{error}</p>}
        <button onClick={handleCompare} disabled={comparing || !baselineId || !targetId}
          className="px-4 py-2 bg-blue-600 text-white text-sm rounded hover:bg-blue-500 disabled:opacity-50">
          {comparing ? "对比中…" : "开始对比"}
        </button>
      </div>

      {result && (
        <div className="space-y-4">
          {/* Overall delta */}
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-5">
              <p className="text-xs text-gray-500 mb-1">准确率变化</p>
              <AccChange val={result.overall.accuracy_change} />
            </div>
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-5">
              <p className="text-xs text-gray-500 mb-1">延迟变化（ms）</p>
              <span className={`text-lg font-semibold ${result.overall.latency_change_ms > 0 ? "text-yellow-400" : "text-green-400"}`}>
                {result.overall.latency_change_ms > 0 ? "+" : ""}{result.overall.latency_change_ms}ms
              </span>
            </div>
          </div>

          {/* Changed results */}
          <div className="grid grid-cols-3 gap-4">
            {[
              { label: "错 → 对", items: result.changed_results.wrong_to_right, color: "text-green-400 border-green-900/30" },
              { label: "对 → 错", items: result.changed_results.right_to_wrong, color: "text-red-400 border-red-900/30" },
              { label: "仍错（答案不同）", items: result.changed_results.still_wrong_different, color: "text-yellow-400 border-yellow-900/30" },
            ].map(({ label, items, color }) => (
              <div key={label} className={`bg-gray-900 border rounded-lg p-4 ${color}`}>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium">{label}</span>
                  <span className="text-2xl font-bold">{items.length}</span>
                </div>
                {items.slice(0, 5).map((qid) => (
                  <p key={qid} className="text-xs text-gray-500 truncate">{qid}</p>
                ))}
                {items.length > 5 && <p className="text-xs text-gray-600 mt-1">…及另 {items.length - 5} 题</p>}
              </div>
            ))}
          </div>

          {/* Run details side by side */}
          <div className="grid grid-cols-2 gap-4">
            {[{ label: "基准", run: result.baseline }, { label: "目标", run: result.target }].map(({ label, run }) => (
              <div key={label} className="bg-gray-900 border border-gray-800 rounded-lg p-4 space-y-1 text-sm">
                <p className="text-xs text-gray-500 font-medium uppercase tracking-wide">{label}</p>
                <p className="text-white font-medium">{run.run_name || run.id.slice(0, 8)}</p>
                <p className="text-gray-400">准确率: {run.accuracy != null ? `${(run.accuracy * 100).toFixed(1)}%` : "—"}</p>
                <p className="text-gray-400">延迟: {run.avg_latency_ms != null ? `${run.avg_latency_ms.toFixed(0)}ms` : "—"}</p>
                <Link href={`/admin/eval/runs/${run.id}`} className="text-blue-400 hover:underline text-xs">查看详情</Link>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
