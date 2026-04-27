"use client";

import { Download, FlaskConical, Loader2, Play, RefreshCw, Trophy } from "lucide-react";
import { useState } from "react";
import type { AbTestTask } from "../types";
import { pct } from "../types";
import { MetricCard, ProgressBar } from "./EvalStatusBits";

const ALL_STRATEGIES = ["parallel", "sequential", "graph_augmented", "gnn"];

interface Props {
  task: AbTestTask | null;
  starting: boolean;
  topK: number;
  error: string | null;
  onFileChange: (file: File | null) => void;
  onTopKChange: (topK: number) => void;
  onStart: (strategies: string[]) => void;
  onRefresh: (taskId: string) => void;
  onDownloadCsv: () => void;
}

export function AbTestTab({
  task,
  starting,
  topK,
  error,
  onFileChange,
  onTopKChange,
  onStart,
  onRefresh,
  onDownloadCsv,
}: Props) {
  const [selected, setSelected] = useState<string[]>(["parallel", "graph_augmented"]);
  const progress = task ? task.completed / Math.max(task.total, 1) : 0;

  function toggleStrategy(s: string) {
    setSelected((prev) =>
      prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s],
    );
  }

  const details = task?.summary?.details ?? [];
  const winner = task?.summary?.winner ?? "";

  return (
    <section className="space-y-6">
      <div className="grid xl:grid-cols-[1.25fr_0.95fr] gap-6">
        <section className="rounded-3xl border border-gray-800 bg-gray-900 p-5 space-y-4">
          <div className="text-white font-medium">A/B 策略对比测试</div>
          <div className="text-sm text-gray-500 leading-6">
            上传与检索 Harness 相同格式的 <code>.jsonl/.csv</code>{" "}
            标注集，同一批问题同时在多个检索策略下执行，自动对比 Hit Rate / MRR /
            NDCG，量化策略优劣。
          </div>

          <label className="block">
            <div className="text-xs text-gray-500 mb-2">标注集文件 (.jsonl / .csv)</div>
            <input
              type="file"
              accept=".jsonl,.csv"
              onChange={(e) => onFileChange(e.target.files?.[0] ?? null)}
              className="block w-full text-sm text-gray-300 file:mr-4 file:px-3 file:py-2 file:rounded-lg file:border-0 file:bg-orange-600 file:text-white hover:file:bg-orange-500"
            />
          </label>

          <div>
            <div className="text-xs text-gray-500 mb-2">参与对比的策略（至少选 2 个）</div>
            <div className="flex flex-wrap gap-2">
              {ALL_STRATEGIES.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => toggleStrategy(s)}
                  className={`px-3 py-1 rounded-lg text-sm transition-colors ${
                    selected.includes(s)
                      ? "bg-orange-600 text-white"
                      : "bg-gray-800 text-gray-400 hover:bg-gray-700"
                  }`}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>

          <label className="block">
            <div className="text-xs text-gray-500 mb-2">Top K</div>
            <input
              type="number"
              min={1}
              max={20}
              value={topK}
              onChange={(e) => onTopKChange(Number(e.target.value || 5))}
              className="w-32 h-10 rounded-lg bg-gray-950 border border-gray-800 px-3 text-sm text-gray-200"
            />
          </label>

          <button
            type="button"
            onClick={() => onStart(selected)}
            disabled={starting || selected.length < 2}
            className="inline-flex items-center gap-2 px-4 h-10 rounded-lg bg-orange-600 text-white hover:bg-orange-500 disabled:opacity-50"
          >
            {starting ? <Loader2 size={15} className="animate-spin" /> : <Play size={15} />}
            开始 A/B 测试
          </button>
        </section>

        <section className="rounded-3xl border border-gray-800 bg-gray-900 p-5 space-y-4">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-white font-medium">
              <FlaskConical size={16} />
              任务状态
            </div>
            {task && (
              <button
                type="button"
                onClick={() => onRefresh(task.task_id)}
                className="inline-flex items-center gap-2 px-3 h-9 rounded-lg border border-gray-700 text-gray-300 hover:text-white hover:border-gray-500 transition-colors"
              >
                <RefreshCw size={14} />
                刷新
              </button>
            )}
          </div>

          {!task && (
            <div className="text-sm text-gray-500">尚未启动 A/B 测试任务。</div>
          )}

          {task && (
            <>
              <div className="grid grid-cols-2 gap-3">
                <MetricCard label="任务状态" value={task.status} />
                <MetricCard label="已完成题目" value={String(task.completed)} tone="emerald" />
              </div>

              <ProgressBar current={task.completed} total={task.total} value={progress} />

              {task.current_question && task.status === "running" && (
                <div className="text-xs text-gray-400 bg-gray-950 border border-gray-800 rounded-xl p-3">
                  正在运行：{task.current_question}
                </div>
              )}

              {winner && (
                <div className="flex items-center gap-2 rounded-xl bg-amber-500/10 border border-amber-500/30 px-4 py-3 text-sm text-amber-300">
                  <Trophy size={15} />
                  最优策略（NDCG）：<span className="font-semibold">{winner}</span>
                </div>
              )}

              {task.status === "completed" && (
                <button
                  type="button"
                  onClick={onDownloadCsv}
                  className="inline-flex items-center gap-2 px-4 h-10 rounded-lg bg-emerald-700 text-white hover:bg-emerald-600"
                >
                  <Download size={15} />
                  导出对比结果 CSV
                </button>
              )}
            </>
          )}
        </section>
      </div>

      {error && (
        <div className="px-4 py-3 rounded-xl bg-red-950/40 border border-red-800/40 text-sm text-red-300">
          {error}
        </div>
      )}

      {details.length > 0 && (
        <div className="overflow-auto rounded-3xl border border-gray-800">
          <table className="w-full text-sm">
            <thead className="bg-gray-950 text-gray-400">
              <tr>
                <th className="px-4 py-3 text-left">排名</th>
                <th className="px-4 py-3 text-left">策略</th>
                <th className="px-4 py-3 text-left">Hit Rate</th>
                <th className="px-4 py-3 text-left">Avg Recall</th>
                <th className="px-4 py-3 text-left">MRR</th>
                <th className="px-4 py-3 text-left">Avg NDCG</th>
                <th className="px-4 py-3 text-left">命中 / 总题</th>
              </tr>
            </thead>
            <tbody>
              {details.map((row, i) => (
                <tr
                  key={row.strategy}
                  className={`align-top border-t border-gray-800 ${
                    row.strategy === winner ? "bg-amber-500/5" : ""
                  }`}
                >
                  <td className="px-4 py-3 text-gray-500">
                    {i === 0 ? (
                      <span className="inline-flex items-center gap-1 text-amber-400">
                        <Trophy size={13} /> 1
                      </span>
                    ) : (
                      i + 1
                    )}
                  </td>
                  <td className="px-4 py-3 font-medium text-gray-200">{row.strategy}</td>
                  <td className="px-4 py-3 text-gray-300">{pct(row.hit_rate)}</td>
                  <td className="px-4 py-3 text-gray-300">{row.avg_recall.toFixed(4)}</td>
                  <td className="px-4 py-3 text-gray-300">{row.mrr.toFixed(4)}</td>
                  <td className="px-4 py-3 text-gray-300 font-medium">{row.avg_ndcg.toFixed(4)}</td>
                  <td className="px-4 py-3 text-gray-400">{row.matched} / {row.total}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
