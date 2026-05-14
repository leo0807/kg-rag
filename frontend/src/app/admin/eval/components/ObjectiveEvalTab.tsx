"use client";

import { Download, FlaskConical, Loader2, Play, RefreshCw } from "lucide-react";
import type { ObjectiveRow, ObjectiveTask } from "../types";
import { pct } from "../types";
import { ObjectiveEvalFilePicker } from "./ObjectiveEvalFilePicker";
import { ObjectiveEvalStageCard } from "./ObjectiveEvalStageCard";

interface Props {
  task: ObjectiveTask | null;
  docId: string;
  selectedFileName: string | null;
  canStart: boolean;
  starting: boolean;
  error: string | null;
  onFileChange: (file: File | null) => void;
  onDocIdChange: (value: string) => void;
  onStart: () => void;
  onRefresh: (taskId: string) => void;
  onDownloadCsv: () => void;
}

export function ObjectiveEvalTab({
  task,
  docId,
  selectedFileName,
  canStart,
  starting,
  error,
  onFileChange,
  onDocIdChange,
  onStart,
  onRefresh,
  onDownloadCsv,
}: Props) {
  const rows: ObjectiveRow[] =
    task?.status === "completed" ? task.results : (task?.results_preview ?? []);
  const progress = task ? task.completed / Math.max(task.total, 1) : 0;

  return (
    <section className="space-y-6">
      <div className="grid xl:grid-cols-[1.25fr_0.95fr] gap-6">
        <section className="rounded-3xl border border-gray-800 bg-gray-900 p-5 space-y-4">
          <div className="text-white font-medium">无答案客观题文档测试</div>
          <div className="text-sm text-gray-500 leading-6">
            上传 `.doc/.docx/.wps`
            客观题文档，系统自动抽题并给出预测答案、依据和来源，不需要标准答案表。
          </div>
          <ObjectiveEvalFilePicker
            selectedFileName={selectedFileName}
            docId={docId}
            onDocIdChange={onDocIdChange}
            onFileChange={onFileChange}
          />
          <div className="rounded-2xl border border-gray-800 bg-gray-950/70 p-4 text-sm text-gray-400 space-y-2 leading-6">
            <div>适合场景：题库 Word / WPS 只有题干和选项，没有标准答案。</div>
            <div>
              输出内容：题号、题干、选项、系统预测答案、依据、引用来源。
            </div>
            <div>
              建议题目格式稳定，题号与选项标识清晰，例如 `1.`、`A.`、`B.`。
            </div>
          </div>

          <button
            type="button"
            onClick={onStart}
            disabled={starting || !canStart}
            className="inline-flex items-center gap-2 px-4 h-10 rounded-lg bg-indigo-600 text-white hover:bg-indigo-500 disabled:opacity-50"
          >
            {starting ? (
              <Loader2 size={15} className="animate-spin" />
            ) : (
              <Play size={15} />
            )}
            开始客观题测试
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
            <div className="text-sm text-gray-500">尚未启动客观题任务。</div>
          )}

          {task && (
            <>
              <ObjectiveEvalStageCard task={task} />

              <div className="grid grid-cols-2 gap-3">
                <InfoCard label="任务状态" value={task.status} />
                <InfoCard label="总题数" value={String(task.total)} />
              </div>

              <ProgressBar
                current={task.completed}
                total={task.total}
                value={progress}
              />

              {task.current_question && task.status === "running" && (
                <div className="text-xs text-gray-400 bg-gray-950 border border-gray-800 rounded-xl p-3">
                  正在作答：{task.current_question}
                </div>
              )}

              {task.summary && (
                <div className="rounded-xl bg-gray-950 border border-gray-800 p-4 text-sm text-gray-300 space-y-1">
                  <div>总题数：{task.summary.total}</div>
                  <div>选择题：{task.summary.choice_count}</div>
                  <div>判断题：{task.summary.judge_count}</div>
                </div>
              )}

              {task.status === "completed" && (
                <button
                  type="button"
                  onClick={onDownloadCsv}
                  className="inline-flex items-center gap-2 px-4 h-10 rounded-lg bg-emerald-700 text-white hover:bg-emerald-600"
                >
                  <Download size={15} />
                  导出预测结果 CSV
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
          <table className="w-full text-sm min-w-[1100px]">
            <thead className="bg-gray-950 text-gray-400">
              <tr>
                <th className="px-4 py-3 text-left">题号</th>
                <th className="px-4 py-3 text-left">题型</th>
                <th className="px-4 py-3 text-left">题目</th>
                <th className="px-4 py-3 text-left">选项</th>
                <th className="px-4 py-3 text-left">预测答案</th>
                <th className="px-4 py-3 text-left">依据</th>
                <th className="px-4 py-3 text-left">来源</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr
                  key={`${row.display_no}-${row.question}`}
                  className="border-t border-gray-800 align-top"
                >
                  <td className="px-4 py-3 text-gray-500">{row.display_no}</td>
                  <td className="px-4 py-3 text-gray-400">
                    {row.question_type}
                  </td>
                  <td className="px-4 py-3 text-gray-200 whitespace-pre-wrap break-words leading-6">
                    {row.question}
                  </td>
                  <td className="px-4 py-3 text-gray-400 whitespace-pre-wrap break-words leading-6">
                    {row.options.length > 0
                      ? row.options
                          .map((opt) => `${opt.label}. ${opt.text}`)
                          .join("\n")
                      : "—"}
                  </td>
                  <td className="px-4 py-3 text-indigo-300 font-medium">
                    {row.predicted_answer || "—"}
                  </td>
                  <td className="px-4 py-3 text-gray-300 whitespace-pre-wrap break-words leading-6">
                    {row.reason || "—"}
                  </td>
                  <td className="px-4 py-3 text-gray-500">
                    {row.source_refs.join(", ") || "—"}
                  </td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr>
                  <td
                    colSpan={7}
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

function InfoCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-gray-950 border border-gray-800 p-4">
      <div className="text-xs text-gray-500">{label}</div>
      <div className="mt-1 text-sm text-white">{value}</div>
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
