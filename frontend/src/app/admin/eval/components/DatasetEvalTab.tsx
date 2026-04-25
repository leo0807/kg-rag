"use client";

import {
  Download,
  FlaskConical,
  Loader2,
  Play,
  RefreshCw,
  Upload,
} from "lucide-react";
import { DATASET_TEMPLATE_CSV } from "../templates";
import type { EvalRow, EvalTask, Strategy } from "../types";
import { pct } from "../types";
import { DatasetResultsTable } from "./DatasetResultsTable";
import { ProgressBar, StatCard } from "./EvalStatusBits";
import { TemplateCard } from "./TemplateCard";

interface Props {
  strategy: Strategy;
  topK: number;
  task: EvalTask | null;
  starting: boolean;
  error: string | null;
  onFileChange: (file: File | null) => void;
  onStrategyChange: (strategy: Strategy) => void;
  onTopKChange: (topK: number) => void;
  onStart: () => void;
  onRefresh: (taskId: string) => void;
  onDownloadCsv: () => void;
}

export function DatasetEvalTab({
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
  const rows: EvalRow[] =
    task?.status === "completed" ? task.results : (task?.results_preview ?? []);
  const progress = task ? task.completed / Math.max(task.total, 1) : 0;

  return (
    <section className="space-y-6">
      <div className="grid xl:grid-cols-[1.25fr_0.95fr] gap-6">
        <section className="rounded-3xl border border-gray-800 bg-gray-900 p-5 space-y-4">
          <div className="flex items-center gap-2 text-white font-medium">
            <Upload size={16} />
            问答标准集
          </div>

          <label className="block">
            <div className="text-xs text-gray-500 mb-2">文件</div>
            <input
              type="file"
              accept=".xlsx,.csv"
              onChange={(e) => onFileChange(e.target.files?.[0] ?? null)}
              className="block w-full text-sm text-gray-300 file:mr-4 file:px-3 file:py-2 file:rounded-lg file:border-0 file:bg-indigo-600 file:text-white hover:file:bg-indigo-500"
            />
          </label>

          <div className="grid md:grid-cols-2 gap-4">
            <label className="block">
              <div className="text-xs text-gray-500 mb-2">检索策略</div>
              <select
                value={strategy}
                onChange={(e) => onStrategyChange(e.target.value as Strategy)}
                className="w-full h-10 rounded-lg bg-gray-950 border border-gray-800 px-3 text-sm text-gray-200"
              >
                <option value="parallel">parallel</option>
                <option value="sequential">sequential</option>
                <option value="graph_augmented">graph_augmented</option>
                <option value="multi_hop">multi_hop</option>
                <option value="counterfactual">counterfactual</option>
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

          <TemplateCard
            title="可直接上传的标准"
            description="支持 CSV / Excel，表头至少包含这 3 列。用户只要保留字段名不变，直接在模板上增删行即可。"
            fields={["问题", "答案", "专业"]}
            sample={DATASET_TEMPLATE_CSV}
            filename="dataset_eval_template.csv"
          />

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
            开始评测
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
            <div className="text-sm text-gray-500">尚未启动评测任务。</div>
          )}

          {task && (
            <>
              <div className="grid grid-cols-2 gap-3">
                <StatCard label="任务状态" value={task.status} />
                <StatCard label="文件" value={task.filename} compact />
                <StatCard
                  label="通过数"
                  value={String(task.passed)}
                  tone="emerald"
                />
                <StatCard
                  label="失败数"
                  value={String(task.failed)}
                  tone="rose"
                />
              </div>

              <ProgressBar label="进度" current={task.completed} total={task.total} value={progress} />

              {task.current_question && task.status === "running" && (
                <div className="text-xs text-gray-400 bg-gray-950 border border-gray-800 rounded-xl p-3">
                  正在评测：{task.current_question}
                </div>
              )}

              {task.summary && (
                <div className="rounded-xl bg-emerald-950/20 border border-emerald-800/40 p-4">
                  <div className="text-xs text-emerald-300/80">最终命中率</div>
                  <div className="mt-1 text-2xl text-emerald-400 font-semibold">
                    {pct(task.summary.pass_rate)}
                  </div>
                </div>
              )}

              {task.status === "completed" && (
                <button
                  type="button"
                  onClick={onDownloadCsv}
                  className="inline-flex items-center gap-2 px-4 h-10 rounded-lg bg-emerald-700 text-white hover:bg-emerald-600"
                >
                  <Download size={15} />
                  导出结果 CSV
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
        <section className="rounded-3xl border border-gray-800 bg-gray-900 overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-800 flex items-center justify-between">
            <div className="text-white font-medium">评测结果</div>
            <div className="text-xs text-gray-500">
              {task.status === "completed"
                ? `共 ${task.results.length} 条`
                : "展示最近执行结果"}
            </div>
          </div>

          <DatasetResultsTable rows={rows} />
        </section>
      )}
    </section>
  );
}
