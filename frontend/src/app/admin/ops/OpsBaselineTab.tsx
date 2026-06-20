"use client";

import { Activity, ArrowRight, Loader2, Play, Shield } from "lucide-react";
import { useState } from "react";
import { fetchApi } from "@/lib/api";
import type { RetrievalBaselineTask } from "./useOpsData";

function pct(value: number) { return `${(value * 100).toFixed(1)}%`; }
function statusTone(status: string) {
  if (status === "running") return "bg-indigo-500/10 text-indigo-300";
  if (status === "completed") return "bg-emerald-500/10 text-emerald-300";
  if (status === "failed") return "bg-red-500/10 text-red-300";
  if (status === "queued") return "bg-amber-500/10 text-amber-300";
  return "bg-gray-800 text-gray-300";
}

interface Props {
  pollRef: { current: number | null };
  onAfterRun: () => void;
}

export function OpsBaselineTab({ pollRef, onAfterRun }: Props) {
  const [task, setTask] = useState<RetrievalBaselineTask | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function pollTask(taskId: string) {
    const data = await fetchApi<RetrievalBaselineTask>(`/api/admin/ops/retrieval-baseline/${taskId}`);
    setTask(data);
    if (data.status === "completed" || data.status === "failed") {
      if (pollRef.current) { window.clearInterval(pollRef.current); pollRef.current = null; }
      onAfterRun();
    }
  }

  async function run() {
    try {
      setLoading(true); setError(null);
      const data = await fetchApi<RetrievalBaselineTask>("/api/admin/ops/retrieval-baseline/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ strategy: "parallel", top_k: 5 }),
      });
      setTask(data);
      if (pollRef.current) window.clearInterval(pollRef.current);
      pollRef.current = window.setInterval(() => pollTask(data.task_id), 1500);
    } catch (err) {
      setError(err instanceof Error ? err.message : "基线回归启动失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <div className="mb-4 flex items-center gap-3">
        <div className="rounded-xl bg-emerald-500/10 p-2"><Play size={18} className="text-emerald-300" /></div>
        <div>
          <h3 className="text-lg font-semibold text-white">检索基线回归</h3>
          <p className="text-xs text-gray-500">直接运行仓库内置 `retrieval_cases.jsonl`，做最小回归。</p>
        </div>
      </div>
      <div className="mb-5 grid grid-cols-1 gap-3 lg:grid-cols-3">
        {[
          { title: "固定样例", text: "使用仓库内置检索测评集验证当前检索策略的基本命中情况。", Icon: Shield },
          { title: "快速回归", text: "适合在修改检索、排序、图谱扩展后快速检查是否出现明显回退。", Icon: Activity },
          { title: "结果可读", text: "会展示命中率、平均召回和 MRR，方便做横向比较。", Icon: ArrowRight },
        ].map(({ title, text, Icon }) => (
          <div key={title} className="rounded-2xl border border-gray-800 bg-gray-950/60 p-4">
            <div className="mb-2 flex items-center gap-2 text-sm font-medium text-white"><Icon size={15} className="text-emerald-300" />{title}</div>
            <div className="text-xs leading-6 text-gray-500">{text}</div>
          </div>
        ))}
      </div>
      {error && <div className="mb-4 rounded-2xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-200">{error}</div>}
      <div className="rounded-2xl border border-gray-800 bg-gray-950/60 p-5">
        <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="text-sm font-medium text-white">内置检索回归任务</div>
            <div className="text-xs text-gray-500">点击后会在后台运行内置案例集，并自动轮询结果。</div>
          </div>
          <button type="button" onClick={run} disabled={loading} className="inline-flex items-center gap-2 rounded-2xl bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50">
            {loading ? <Loader2 size={15} className="animate-spin" /> : <Play size={15} />}
            运行内置回归
          </button>
        </div>
        <div className="rounded-2xl border border-gray-800 bg-gray-900/70 p-4">
          {!task && <div className="text-sm text-gray-500">还没有启动本轮基线回归。</div>}
          {task && (
            <div className="space-y-3">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-sm font-medium text-white">{task.filename}</div>
                  <div className="text-xs text-gray-500">task: {task.task_id}</div>
                </div>
                <span className={`rounded-full px-2.5 py-1 text-[10px] uppercase tracking-widest ${statusTone(task.status)}`}>{task.status}</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-gray-950">
                <div className="h-full rounded-full bg-emerald-500 transition-all" style={{ width: `${Math.round((task.completed / Math.max(task.total, 1)) * 100)}%` }} />
              </div>
              <div className="flex flex-wrap gap-4 text-xs text-gray-400">
                <span>进度 {task.completed}/{task.total}</span>
                {task.summary && (
                  <>
                    <span>命中率 {pct(task.summary.hit_rate)}</span>
                    <span>平均召回 {pct(task.summary.avg_recall)}</span>
                    <span>MRR {(task.summary.mrr ?? 0).toFixed(3)}</span>
                  </>
                )}
              </div>
              {task.current_question && task.status === "running" && <div className="text-sm text-gray-300">当前问题：{task.current_question}</div>}
              {task.error && <div className="text-sm text-red-300">{task.error}</div>}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
