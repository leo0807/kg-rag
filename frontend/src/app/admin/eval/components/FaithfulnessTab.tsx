"use client";

import { Download, FlaskConical, Loader2, Play, RefreshCw } from "lucide-react";
import type { FaithfulnessRow, FaithfulnessTask } from "../types";
import { pct } from "../types";
import { MetricCard, ProgressBar } from "./EvalStatusBits";

const SAMPLE_JSONL = `{"question":"铝合金焊接前表面处理要求是什么？","answer":"铝合金焊接前需打磨氧化层并用丙酮擦拭。","passages":["铝合金焊接前需打磨氧化层并用丙酮清洁焊缝两侧各25mm。","焊接电流应根据板厚调整。"]}`;

interface Props {
  task: FaithfulnessTask | null;
  starting: boolean;
  error: string | null;
  onFileChange: (file: File | null) => void;
  onStart: () => void;
  onRefresh: (taskId: string) => void;
  onDownloadCsv: () => void;
}

export function FaithfulnessTab({
  task,
  starting,
  error,
  onFileChange,
  onStart,
  onRefresh,
  onDownloadCsv,
}: Props) {
  const rows: FaithfulnessRow[] =
    task?.status === "completed" ? task.results : (task?.results_preview ?? []);
  const progress = task ? task.completed / Math.max(task.total, 1) : 0;

  return (
    <section className="space-y-6">
      <div className="grid xl:grid-cols-[1.25fr_0.95fr] gap-6">
        <section className="rounded-3xl border border-gray-800 bg-gray-900 p-5 space-y-4">
          <div className="text-white font-medium">忠实度评测（Faithfulness）</div>
          <div className="text-sm text-gray-500 leading-6">
            上传 <code>.jsonl</code> 文件，每行包含 <code>question</code>、
            <code>answer</code> 和 <code>passages</code>（数组）三个字段，LLM
            将判断回答是否完全基于参考段落，检测幻觉内容。
          </div>

          <div className="rounded-xl border border-gray-800 bg-gray-950 p-4 text-xs font-mono text-gray-400 overflow-auto">
            <div className="text-gray-500 mb-2"># 示例行</div>
            {SAMPLE_JSONL}
          </div>

          <label className="block">
            <div className="text-xs text-gray-500 mb-2">忠实度评测文件 (.jsonl)</div>
            <input
              type="file"
              accept=".jsonl"
              onChange={(e) => onFileChange(e.target.files?.[0] ?? null)}
              className="block w-full text-sm text-gray-300 file:mr-4 file:px-3 file:py-2 file:rounded-lg file:border-0 file:bg-violet-600 file:text-white hover:file:bg-violet-500"
            />
          </label>

          <button
            type="button"
            onClick={onStart}
            disabled={starting}
            className="inline-flex items-center gap-2 px-4 h-10 rounded-lg bg-violet-600 text-white hover:bg-violet-500 disabled:opacity-50"
          >
            {starting ? <Loader2 size={15} className="animate-spin" /> : <Play size={15} />}
            开始忠实度检测
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
            <div className="text-sm text-gray-500">尚未启动忠实度评测任务。</div>
          )}

          {task && (
            <>
              <div className="grid grid-cols-2 gap-3">
                <MetricCard label="任务状态" value={task.status} />
                <MetricCard
                  label="忠实数"
                  value={String(task.faithful_count)}
                  tone="emerald"
                />
              </div>

              <ProgressBar current={task.completed} total={task.total} value={progress} />

              {task.current_question && task.status === "running" && (
                <div className="text-xs text-gray-400 bg-gray-950 border border-gray-800 rounded-xl p-3">
                  正在检测：{task.current_question}
                </div>
              )}

              {task.summary && (
                <div className="rounded-xl bg-gray-950 border border-gray-800 p-4 text-sm text-gray-300 space-y-1">
                  <div>忠实度：{pct(task.summary.faithfulness_rate)}</div>
                  <div>Avg Score：{task.summary.avg_score.toFixed(4)}</div>
                  <div>忠实 / 幻觉：{task.summary.faithful_count} / {task.summary.unfaithful_count}</div>
                </div>
              )}

              {task.status === "completed" && (
                <button
                  type="button"
                  onClick={onDownloadCsv}
                  className="inline-flex items-center gap-2 px-4 h-10 rounded-lg bg-emerald-700 text-white hover:bg-emerald-600"
                >
                  <Download size={15} />
                  导出忠实度结果 CSV
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

      {rows.length > 0 && (
        <div className="overflow-auto rounded-3xl border border-gray-800">
          <table className="min-w-[1200px] w-full text-sm">
            <thead className="bg-gray-950 text-gray-400">
              <tr>
                <th className="px-4 py-3 text-left">行号</th>
                <th className="px-4 py-3 text-left">结果</th>
                <th className="px-4 py-3 text-left">Score</th>
                <th className="px-4 py-3 text-left">问题</th>
                <th className="px-4 py-3 text-left">回答</th>
                <th className="px-4 py-3 text-left">无依据声明</th>
                <th className="px-4 py-3 text-left">原因</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.row_no} className="align-top border-t border-gray-800">
                  <td className="px-4 py-3 text-gray-500">{row.row_no}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-flex rounded-full px-2 py-1 text-xs font-medium ${
                        row.faithful
                          ? "bg-emerald-500/15 text-emerald-400"
                          : "bg-rose-500/15 text-rose-400"
                      }`}
                    >
                      {row.faithful ? "忠实" : "幻觉"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-400">{row.score.toFixed(2)}</td>
                  <td className="whitespace-pre-wrap px-4 py-3 text-gray-200 max-w-[220px]">{row.question}</td>
                  <td className="whitespace-pre-wrap px-4 py-3 text-gray-300 max-w-[240px]">{row.answer}</td>
                  <td className="px-4 py-3 text-rose-300 max-w-[200px]">
                    {row.unsupported_claims.length > 0 ? row.unsupported_claims.join("；") : "—"}
                  </td>
                  <td className="px-4 py-3 text-gray-400 max-w-[200px]">{row.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
