"use client";

import { Download, FlaskConical, Loader2, Play, RefreshCw } from "lucide-react";
import { RETRIEVAL_TEMPLATE_CSV, RETRIEVAL_TEMPLATE_JSONL } from "../templates";
import type { RetrievalRow, RetrievalStrategy, RetrievalTask } from "../types";
import { pct } from "../types";
import { TemplateCard } from "./TemplateCard";

interface Props {
  strategy: RetrievalStrategy;
  topK: number;
  task: RetrievalTask | null;
  starting: boolean;
  error: string | null;
  onFileChange: (file: File | null) => void;
  onStrategyChange: (strategy: RetrievalStrategy) => void;
  onTopKChange: (topK: number) => void;
  onStart: () => void;
  onRefresh: (taskId: string) => void;
  onDownloadCsv: () => void;
}

export function RetrievalEvalTab({
  strategy,
  topK,
  task,
  starting,
  error,
  onFileChange,
  onStrategyChange,
  onTopKChange,
  onStart,
  onRefresh,
  onDownloadCsv,
}: Props) {
  const rows: RetrievalRow[] =
    task?.status === "completed" ? task.results : (task?.results_preview ?? []);
  const progress = task ? task.completed / Math.max(task.total, 1) : 0;

  return (
    <section className="space-y-6">
      <div className="grid xl:grid-cols-[1.25fr_0.95fr] gap-6">
        <section className="rounded-3xl border border-gray-800 bg-gray-900 p-5 space-y-4">
          <div className="text-white font-medium">检索 Harness</div>
          <div className="text-sm text-gray-500 leading-6">
            上传 `.jsonl/.csv` 标注集，直接评估检索命中率、平均召回率和 MRR，
            不经过答案生成。
          </div>

          <label className="block">
            <div className="text-xs text-gray-500 mb-2">检索评测文件</div>
            <input
              type="file"
              accept=".jsonl,.csv"
              onChange={(e) => onFileChange(e.target.files?.[0] ?? null)}
              className="block w-full text-sm text-gray-300 file:mr-4 file:px-3 file:py-2 file:rounded-lg file:border-0 file:bg-indigo-600 file:text-white hover:file:bg-indigo-500"
            />
          </label>

          <div className="grid md:grid-cols-2 gap-4">
            <label className="block">
              <div className="text-xs text-gray-500 mb-2">检索策略</div>
              <select
                value={strategy}
                onChange={(e) =>
                  onStrategyChange(e.target.value as RetrievalStrategy)
                }
                className="w-full h-10 rounded-lg bg-gray-950 border border-gray-800 px-3 text-sm text-gray-200"
              >
                <option value="parallel">parallel</option>
                <option value="sequential">sequential</option>
                <option value="graph_augmented">graph_augmented</option>
                <option value="gnn">gnn</option>
              </select>
            </label>

            <label className="block">
              <div className="text-xs text-gray-500 mb-2">Top K</div>
              <input
                type="number"
                min={1}
                max={20}
                value={topK}
                onChange={(e) => onTopKChange(Number(e.target.value || 5))}
                className="w-full h-10 rounded-lg bg-gray-950 border border-gray-800 px-3 text-sm text-gray-200"
              />
            </label>
          </div>

          <div className="grid gap-4">
            <TemplateCard
              title="JSONL 标准"
              description="推荐格式。每行一个 JSON 对象，最少提供 question + gold_chunk_ids 或 gold_doc_ids。"
              fields={[
                "question",
                "gold_chunk_ids",
                "gold_doc_ids",
                "domain",
                "strategy",
              ]}
              sample={RETRIEVAL_TEMPLATE_JSONL}
              filename="retrieval_harness_template.jsonl"
            />
            <TemplateCard
              title="CSV 标准"
              description="适合业务同学直接改表。数组列可写成逗号分隔值或直接沿用模板。"
              fields={[
                "question",
                "gold_chunk_ids",
                "gold_doc_ids",
                "domain",
                "strategy",
              ]}
              sample={RETRIEVAL_TEMPLATE_CSV}
              filename="retrieval_harness_template.csv"
            />
          </div>

          <button
            type="button"
            onClick={onStart}
            disabled={starting}
            className="inline-flex items-center gap-2 px-4 h-10 rounded-lg bg-indigo-600 text-white hover:bg-indigo-500 disabled:opacity-50"
          >
            {starting ? (
              <Loader2 size={15} className="animate-spin" />
            ) : (
              <Play size={15} />
            )}
            开始检索评测
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
            <div className="text-sm text-gray-500">尚未启动检索评测任务。</div>
          )}

          {task && (
            <>
              <div className="grid grid-cols-2 gap-3">
                <MetricCard label="任务状态" value={task.status} />
                <MetricCard
                  label="命中数"
                  value={String(task.matched)}
                  tone="emerald"
                />
              </div>

              <ProgressBar
                current={task.completed}
                total={task.total}
                value={progress}
              />

              {task.current_question && task.status === "running" && (
                <div className="text-xs text-gray-400 bg-gray-950 border border-gray-800 rounded-xl p-3">
                  正在检索：{task.current_question}
                </div>
              )}

              {task.summary && (
                <div className="rounded-xl bg-gray-950 border border-gray-800 p-4 text-sm text-gray-300 space-y-1">
                  <div>Hit Rate：{pct(task.summary.hit_rate)}</div>
                  <div>Avg Recall：{task.summary.avg_recall.toFixed(4)}</div>
                  <div>MRR：{task.summary.mrr.toFixed(4)}</div>
                  <div>Chunk 标注：{task.summary.chunk_target_count}</div>
                  <div>Doc 标注：{task.summary.doc_target_count}</div>
                </div>
              )}

              {task.status === "completed" && (
                <button
                  type="button"
                  onClick={onDownloadCsv}
                  className="inline-flex items-center gap-2 px-4 h-10 rounded-lg bg-emerald-700 text-white hover:bg-emerald-600"
                >
                  <Download size={15} />
                  导出检索结果 CSV
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

      {task && (
        <div className="overflow-auto rounded-3xl border border-gray-800">
          <table className="w-full text-sm min-w-[1300px]">
            <thead className="bg-gray-950 text-gray-400">
              <tr>
                <th className="px-4 py-3 text-left">行号</th>
                <th className="px-4 py-3 text-left">结果</th>
                <th className="px-4 py-3 text-left">目标</th>
                <th className="px-4 py-3 text-left">问题</th>
                <th className="px-4 py-3 text-left">Gold Chunk</th>
                <th className="px-4 py-3 text-left">Gold Doc</th>
                <th className="px-4 py-3 text-left">命中位置</th>
                <th className="px-4 py-3 text-left">Recall</th>
                <th className="px-4 py-3 text-left">RR</th>
                <th className="px-4 py-3 text-left">检索结果</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr
                  key={`${row.row_no}-${row.question}`}
                  className="border-t border-gray-800 align-top"
                >
                  <td className="px-4 py-3 text-gray-500">{row.row_no}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-flex px-2 py-1 rounded-full text-xs font-medium ${
                        row.matched
                          ? "bg-emerald-500/15 text-emerald-400"
                          : "bg-rose-500/15 text-rose-400"
                      }`}
                    >
                      {row.matched ? "PASS" : "FAIL"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-400">{row.target_type}</td>
                  <td className="px-4 py-3 text-gray-200 whitespace-pre-wrap">
                    {row.question}
                  </td>
                  <td className="px-4 py-3 text-gray-400">
                    {row.gold_chunk_ids.join(", ") || "—"}
                  </td>
                  <td className="px-4 py-3 text-gray-400">
                    {row.gold_doc_ids.join(", ") || "—"}
                  </td>
                  <td className="px-4 py-3 text-gray-400">
                    {row.hit_rank ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-gray-400">
                    {row.recall.toFixed(4)}
                  </td>
                  <td className="px-4 py-3 text-gray-400">
                    {row.reciprocal_rank.toFixed(4)}
                  </td>
                  <td className="px-4 py-3 text-gray-500">
                    {row.retrieved_chunk_ids.join(", ") ||
                      row.source_refs.join(", ") ||
                      "—"}
                  </td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr>
                  <td
                    colSpan={10}
                    className="px-4 py-10 text-center text-gray-500"
                  >
                    暂无结果
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function MetricCard({
  label,
  value,
  tone = "default",
}: {
  label: string;
  value: string;
  tone?: "default" | "emerald";
}) {
  return (
    <div className="rounded-xl bg-gray-950 border border-gray-800 p-4">
      <div className="text-xs text-gray-500">{label}</div>
      <div
        className={`mt-1 text-lg ${
          tone === "emerald" ? "text-emerald-400" : "text-white"
        }`}
      >
        {value}
      </div>
    </div>
  );
}

function ProgressBar({
  current,
  total,
  value,
}: {
  current: number;
  total: number;
  value: number;
}) {
  return (
    <div>
      <div className="flex justify-between text-xs text-gray-500 mb-2">
        <span>进度</span>
        <span>
          {current}/{total}
        </span>
      </div>
      <div className="h-2 rounded-full bg-gray-800 overflow-hidden">
        <div
          className="h-full bg-indigo-500 transition-all"
          style={{ width: pct(value) }}
        />
      </div>
    </div>
  );
}
