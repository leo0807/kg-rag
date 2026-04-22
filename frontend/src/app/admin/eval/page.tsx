"use client";

import {
  Download,
  FlaskConical,
  Loader2,
  Play,
  RefreshCw,
  Upload,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { fetchApi } from "@/lib/api";

const API = "http://localhost:8000";

type Strategy =
  | "parallel"
  | "sequential"
  | "graph_augmented"
  | "multi_hop"
  | "counterfactual"
  | "gnn";
type RetrievalStrategy = "parallel" | "sequential" | "graph_augmented" | "gnn";

interface EvalRow {
  row_no: number;
  question: string;
  expected_answer: string;
  actual_answer: string;
  domain: string;
  matched: boolean;
  similarity: number;
  source_refs: string[];
}

interface EvalTask {
  task_id: string;
  filename: string;
  status: "queued" | "running" | "completed" | "failed";
  strategy: Strategy;
  top_k: number;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  total: number;
  completed: number;
  passed: number;
  failed: number;
  current_question: string;
  error: string;
  summary: {
    total: number;
    passed: number;
    failed: number;
    pass_rate: number;
  } | null;
  results_preview: EvalRow[];
  results: EvalRow[];
}

interface ObjectiveOption {
  label: string;
  text: string;
}

interface ObjectiveRow {
  display_no: string;
  question: string;
  options: ObjectiveOption[];
  question_type: string;
  predicted_answer: string;
  reason: string;
  source_refs: string[];
}

interface ObjectiveTask {
  task_id: string;
  filename: string;
  status: "queued" | "running" | "completed" | "failed";
  strategy: Strategy;
  top_k: number;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  total: number;
  completed: number;
  current_question: string;
  error: string;
  summary: { total: number; choice_count: number; judge_count: number } | null;
  results_preview: ObjectiveRow[];
  results: ObjectiveRow[];
}

interface RetrievalRow {
  row_no: number;
  question: string;
  domain: string;
  strategy: RetrievalStrategy;
  target_type: "chunk" | "doc";
  gold_chunk_ids: string[];
  gold_doc_ids: string[];
  retrieved_chunk_ids: string[];
  retrieved_doc_ids: string[];
  matched: boolean;
  hit_rank: number | null;
  recall: number;
  reciprocal_rank: number;
  source_refs: string[];
}

interface RetrievalTask {
  task_id: string;
  filename: string;
  status: "queued" | "running" | "completed" | "failed";
  strategy: RetrievalStrategy;
  top_k: number;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  total: number;
  completed: number;
  matched: number;
  unmatched: number;
  current_question: string;
  error: string;
  summary: {
    total: number;
    matched: number;
    unmatched: number;
    hit_rate: number;
    avg_recall: number;
    mrr: number;
    chunk_target_count: number;
    doc_target_count: number;
  } | null;
  results_preview: RetrievalRow[];
  results: RetrievalRow[];
}

function pct(v: number) {
  return `${(v * 100).toFixed(1)}%`;
}

export default function AdminEvalPage() {
  const [file, setFile] = useState<File | null>(null);
  const [strategy, setStrategy] = useState<Strategy>("parallel");
  const [topK, setTopK] = useState(5);
  const [task, setTask] = useState<EvalTask | null>(null);
  const [starting, setStarting] = useState(false);
  const [objectiveFile, setObjectiveFile] = useState<File | null>(null);
  const [objectiveTask, setObjectiveTask] = useState<ObjectiveTask | null>(
    null,
  );
  const [objectiveStarting, setObjectiveStarting] = useState(false);
  const [retrievalFile, setRetrievalFile] = useState<File | null>(null);
  const [retrievalStrategy, setRetrievalStrategy] =
    useState<RetrievalStrategy>("parallel");
  const [retrievalTask, setRetrievalTask] = useState<RetrievalTask | null>(
    null,
  );
  const [retrievalStarting, setRetrievalStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<number | null>(null);
  const objectiveTimerRef = useRef<number | null>(null);
  const retrievalTimerRef = useRef<number | null>(null);

  async function loadTask(taskId: string) {
    const data = await fetchApi<EvalTask>(
      `${API}/api/admin/eval/dataset/${taskId}`,
    );
    setTask(data);
    if (data.status === "completed" || data.status === "failed") {
      if (timerRef.current) {
        window.clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }
  }

  useEffect(
    () => () => {
      if (timerRef.current) window.clearInterval(timerRef.current);
      if (objectiveTimerRef.current)
        window.clearInterval(objectiveTimerRef.current);
      if (retrievalTimerRef.current)
        window.clearInterval(retrievalTimerRef.current);
    },
    [],
  );

  async function loadObjectiveTask(taskId: string) {
    const data = await fetchApi<ObjectiveTask>(
      `${API}/api/admin/eval/objective-doc/${taskId}`,
    );
    setObjectiveTask(data);
    if (data.status === "completed" || data.status === "failed") {
      if (objectiveTimerRef.current) {
        window.clearInterval(objectiveTimerRef.current);
        objectiveTimerRef.current = null;
      }
    }
  }

  async function loadRetrievalTask(taskId: string) {
    const data = await fetchApi<RetrievalTask>(
      `${API}/api/admin/eval/retrieval/${taskId}`,
    );
    setRetrievalTask(data);
    if (data.status === "completed" || data.status === "failed") {
      if (retrievalTimerRef.current) {
        window.clearInterval(retrievalTimerRef.current);
        retrievalTimerRef.current = null;
      }
    }
  }

  async function handleStart() {
    if (!file) {
      setError("请先选择测试集文件");
      return;
    }
    setStarting(true);
    setError(null);
    try {
      const token = localStorage.getItem("token") ?? "";
      const fd = new FormData();
      fd.append("file", file);
      fd.append("strategy", strategy);
      fd.append("top_k", String(topK));

      const res = await fetch(`${API}/api/admin/eval/dataset`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: fd,
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({ detail: "启动评测失败" }));
        throw new Error(body.detail || "启动评测失败");
      }
      const data = (await res.json()) as EvalTask;
      setTask(data);

      if (timerRef.current) window.clearInterval(timerRef.current);
      timerRef.current = window.setInterval(() => {
        loadTask(data.task_id);
      }, 1500);
    } catch (e) {
      setError(e instanceof Error ? e.message : "启动评测失败");
    } finally {
      setStarting(false);
    }
  }

  function downloadCsv() {
    if (!task) return;
    const token = localStorage.getItem("token") ?? "";
    fetch(`${API}/api/admin/eval/dataset/${task.task_id}/csv`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => {
        if (!r.ok) throw new Error("导出失败");
        return r.blob();
      })
      .then((blob) => {
        const href = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = href;
        a.download = `${task.filename.replace(/\.(xlsx|csv)$/i, "")}_results.csv`;
        a.click();
        URL.revokeObjectURL(href);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "导出失败"));
  }

  async function handleStartObjective() {
    if (!objectiveFile) {
      setError("请先选择客观题文档");
      return;
    }
    setObjectiveStarting(true);
    setError(null);
    try {
      const token = localStorage.getItem("token") ?? "";
      const fd = new FormData();
      fd.append("file", objectiveFile);
      fd.append("strategy", strategy);
      fd.append("top_k", String(topK));

      const res = await fetch(`${API}/api/admin/eval/objective-doc`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: fd,
      });
      if (!res.ok) {
        const body = await res
          .json()
          .catch(() => ({ detail: "启动客观题测试失败" }));
        throw new Error(body.detail || "启动客观题测试失败");
      }
      const data = (await res.json()) as ObjectiveTask;
      setObjectiveTask(data);

      if (objectiveTimerRef.current)
        window.clearInterval(objectiveTimerRef.current);
      objectiveTimerRef.current = window.setInterval(() => {
        loadObjectiveTask(data.task_id);
      }, 1500);
    } catch (e) {
      setError(e instanceof Error ? e.message : "启动客观题测试失败");
    } finally {
      setObjectiveStarting(false);
    }
  }

  function downloadObjectiveCsv() {
    if (!objectiveTask) return;
    const token = localStorage.getItem("token") ?? "";
    fetch(`${API}/api/admin/eval/objective-doc/${objectiveTask.task_id}/csv`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => {
        if (!r.ok) throw new Error("导出失败");
        return r.blob();
      })
      .then((blob) => {
        const href = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = href;
        a.download = `${objectiveTask.filename.replace(/\.(docx|doc|wps)$/i, "")}_predictions.csv`;
        a.click();
        URL.revokeObjectURL(href);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "导出失败"));
  }

  async function handleStartRetrieval() {
    if (!retrievalFile) {
      setError("请先选择检索评测文件");
      return;
    }
    setRetrievalStarting(true);
    setError(null);
    try {
      const token = localStorage.getItem("token") ?? "";
      const fd = new FormData();
      fd.append("file", retrievalFile);
      fd.append("strategy", retrievalStrategy);
      fd.append("top_k", String(topK));

      const res = await fetch(`${API}/api/admin/eval/retrieval`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: fd,
      });
      if (!res.ok) {
        const body = await res
          .json()
          .catch(() => ({ detail: "启动检索评测失败" }));
        throw new Error(body.detail || "启动检索评测失败");
      }
      const data = (await res.json()) as RetrievalTask;
      setRetrievalTask(data);

      if (retrievalTimerRef.current)
        window.clearInterval(retrievalTimerRef.current);
      retrievalTimerRef.current = window.setInterval(() => {
        loadRetrievalTask(data.task_id);
      }, 1500);
    } catch (e) {
      setError(e instanceof Error ? e.message : "启动检索评测失败");
    } finally {
      setRetrievalStarting(false);
    }
  }

  function downloadRetrievalCsv() {
    if (!retrievalTask) return;
    const token = localStorage.getItem("token") ?? "";
    fetch(`${API}/api/admin/eval/retrieval/${retrievalTask.task_id}/csv`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => {
        if (!r.ok) throw new Error("导出失败");
        return r.blob();
      })
      .then((blob) => {
        const href = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = href;
        a.download = `${retrievalTask.filename.replace(/\.(jsonl|csv)$/i, "")}_retrieval.csv`;
        a.click();
        URL.revokeObjectURL(href);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "导出失败"));
  }

  const rows =
    task?.status === "completed" ? task.results : (task?.results_preview ?? []);
  const progress = task ? task.completed / Math.max(task.total, 1) : 0;
  const objectiveRows =
    objectiveTask?.status === "completed"
      ? objectiveTask.results
      : (objectiveTask?.results_preview ?? []);
  const objectiveProgress = objectiveTask
    ? objectiveTask.completed / Math.max(objectiveTask.total, 1)
    : 0;
  const retrievalRows =
    retrievalTask?.status === "completed"
      ? retrievalTask.results
      : (retrievalTask?.results_preview ?? []);
  const retrievalProgress = retrievalTask
    ? retrievalTask.completed / Math.max(retrievalTask.total, 1)
    : 0;

  return (
    <div className="flex-1 overflow-auto bg-gray-950 p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white">测试集评测</h1>
          <p className="text-sm text-gray-500 mt-1">
            上传 Excel/CSV
            测试集，系统将逐条执行智能问答并生成命中率统计与结果明细。
          </p>
        </div>
        {task && (
          <button
            type="button"
            onClick={() => loadTask(task.task_id)}
            className="flex items-center gap-2 px-3 h-9 rounded-lg border border-gray-700 text-gray-300 hover:text-white hover:border-gray-500 transition-colors"
          >
            <RefreshCw size={14} />
            刷新状态
          </button>
        )}
      </div>

      <div className="grid lg:grid-cols-[1.3fr_1fr] gap-6">
        <section className="bg-gray-900 border border-gray-800 rounded-2xl p-5 space-y-4">
          <div className="flex items-center gap-2 text-white font-medium">
            <Upload size={16} />
            上传测试集
          </div>

          <label className="block">
            <div className="text-xs text-gray-500 mb-2">文件</div>
            <input
              type="file"
              accept=".xlsx,.csv"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="block w-full text-sm text-gray-300 file:mr-4 file:px-3 file:py-2 file:rounded-lg file:border-0 file:bg-indigo-600 file:text-white hover:file:bg-indigo-500"
            />
          </label>

          <div className="grid md:grid-cols-2 gap-4">
            <label className="block">
              <div className="text-xs text-gray-500 mb-2">检索策略</div>
              <select
                value={strategy}
                onChange={(e) => setStrategy(e.target.value as Strategy)}
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
                onChange={(e) => setTopK(Number(e.target.value || 5))}
                className="w-full h-10 rounded-lg bg-gray-950 border border-gray-800 px-3 text-sm text-gray-200"
              />
            </label>
          </div>

          <div className="rounded-xl border border-gray-800 bg-gray-950 p-4 text-sm text-gray-400">
            <div>当前支持列名：`问题`、`答案`、`专业`。</div>
            <div className="mt-1">
              这份你提供的文件表头已匹配，可直接上传运行。
            </div>
          </div>

          <button
            type="button"
            onClick={handleStart}
            disabled={starting}
            className="flex items-center gap-2 px-4 h-10 rounded-lg bg-indigo-600 text-white hover:bg-indigo-500 disabled:opacity-50"
          >
            {starting ? (
              <Loader2 size={15} className="animate-spin" />
            ) : (
              <Play size={15} />
            )}
            开始评测
          </button>
        </section>

        <section className="bg-gray-900 border border-gray-800 rounded-2xl p-5 space-y-4">
          <div className="flex items-center gap-2 text-white font-medium">
            <FlaskConical size={16} />
            任务状态
          </div>

          {!task && (
            <div className="text-sm text-gray-500">尚未启动评测任务。</div>
          )}

          {task && (
            <>
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-xl bg-gray-950 border border-gray-800 p-4">
                  <div className="text-xs text-gray-500">任务状态</div>
                  <div className="mt-1 text-sm text-white">{task.status}</div>
                </div>
                <div className="rounded-xl bg-gray-950 border border-gray-800 p-4">
                  <div className="text-xs text-gray-500">文件</div>
                  <div className="mt-1 text-sm text-white truncate">
                    {task.filename}
                  </div>
                </div>
                <div className="rounded-xl bg-gray-950 border border-gray-800 p-4">
                  <div className="text-xs text-gray-500">通过数</div>
                  <div className="mt-1 text-lg text-emerald-400">
                    {task.passed}
                  </div>
                </div>
                <div className="rounded-xl bg-gray-950 border border-gray-800 p-4">
                  <div className="text-xs text-gray-500">失败数</div>
                  <div className="mt-1 text-lg text-rose-400">
                    {task.failed}
                  </div>
                </div>
              </div>

              <div>
                <div className="flex justify-between text-xs text-gray-500 mb-2">
                  <span>进度</span>
                  <span>
                    {task.completed}/{task.total}
                  </span>
                </div>
                <div className="h-2 rounded-full bg-gray-800 overflow-hidden">
                  <div
                    className="h-full bg-indigo-500 transition-all"
                    style={{ width: pct(progress) }}
                  />
                </div>
              </div>

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
                  onClick={downloadCsv}
                  className="flex items-center gap-2 px-4 h-10 rounded-lg bg-emerald-700 text-white hover:bg-emerald-600"
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
        <section className="bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-800 flex items-center justify-between">
            <div className="text-white font-medium">评测结果</div>
            <div className="text-xs text-gray-500">
              {task.status === "completed"
                ? `共 ${task.results.length} 条`
                : "展示最近执行结果"}
            </div>
          </div>

          <div className="overflow-auto">
            <table className="w-full text-sm min-w-[1100px]">
              <thead className="bg-gray-950 text-gray-400">
                <tr>
                  <th className="px-4 py-3 text-left">行号</th>
                  <th className="px-4 py-3 text-left">结果</th>
                  <th className="px-4 py-3 text-left">问题</th>
                  <th className="px-4 py-3 text-left">标准答案</th>
                  <th className="px-4 py-3 text-left">系统答案</th>
                  <th className="px-4 py-3 text-left">相似度</th>
                  <th className="px-4 py-3 text-left">来源</th>
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
                    <td className="px-4 py-3 text-gray-200 whitespace-pre-wrap">
                      {row.question}
                    </td>
                    <td className="px-4 py-3 text-gray-400 whitespace-pre-wrap">
                      {row.expected_answer}
                    </td>
                    <td className="px-4 py-3 text-gray-300 whitespace-pre-wrap">
                      {row.actual_answer}
                    </td>
                    <td className="px-4 py-3 text-gray-400">
                      {row.similarity.toFixed(4)}
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
        </section>
      )}

      <section className="bg-gray-900 border border-gray-800 rounded-2xl p-5 space-y-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0">
            <div className="text-white font-medium">无答案客观题文档测试</div>
            <div className="text-sm text-gray-500 mt-1">
              上传 `.doc/.docx/.wps`
              客观题文档，系统自动抽题并给出预测答案、依据和来源，不需要标准答案。
            </div>
          </div>
          {objectiveTask && (
            <button
              type="button"
              onClick={() => loadObjectiveTask(objectiveTask.task_id)}
              className="inline-flex items-center justify-center gap-2 px-3 h-9 rounded-lg border border-gray-700 text-gray-300 hover:text-white hover:border-gray-500 transition-colors self-start sm:self-auto w-full sm:w-auto"
            >
              <RefreshCw size={14} />
              刷新状态
            </button>
          )}
        </div>

        <div className="grid lg:grid-cols-[1.3fr_1fr] gap-6">
          <section className="rounded-2xl border border-gray-800 bg-gray-950 p-5 space-y-4">
            <label className="block">
              <div className="text-xs text-gray-500 mb-2">客观题文档</div>
              <input
                type="file"
                accept=".doc,.docx,.wps"
                onChange={(e) => setObjectiveFile(e.target.files?.[0] ?? null)}
                className="block w-full text-sm text-gray-300 file:mr-4 file:px-3 file:py-2 file:rounded-lg file:border-0 file:bg-indigo-600 file:text-white hover:file:bg-indigo-500"
              />
            </label>

            <div className="rounded-xl border border-gray-800 bg-gray-900 p-4 text-sm text-gray-400 space-y-1">
              <div>适合场景：题库 Word/WPS 只有题干和选项，没有标准答案。</div>
              <div>
                输出内容：题号、题干、选项、系统预测答案、依据、引用来源。
              </div>
              <div>你给的这份 `.wps` 已确认可被 LibreOffice 转换并抽题。</div>
            </div>

            <button
              type="button"
              onClick={handleStartObjective}
              disabled={objectiveStarting}
              className="flex items-center gap-2 px-4 h-10 rounded-lg bg-indigo-600 text-white hover:bg-indigo-500 disabled:opacity-50"
            >
              {objectiveStarting ? (
                <Loader2 size={15} className="animate-spin" />
              ) : (
                <Play size={15} />
              )}
              开始客观题测试
            </button>
          </section>

          <section className="rounded-2xl border border-gray-800 bg-gray-950 p-5 space-y-4">
            {!objectiveTask && (
              <div className="text-sm text-gray-500">尚未启动客观题任务。</div>
            )}
            {objectiveTask && (
              <>
                <div className="grid grid-cols-2 gap-3">
                  <div className="rounded-xl bg-gray-900 border border-gray-800 p-4">
                    <div className="text-xs text-gray-500">任务状态</div>
                    <div className="mt-1 text-sm text-white">
                      {objectiveTask.status}
                    </div>
                  </div>
                  <div className="rounded-xl bg-gray-900 border border-gray-800 p-4">
                    <div className="text-xs text-gray-500">总题数</div>
                    <div className="mt-1 text-sm text-white">
                      {objectiveTask.total}
                    </div>
                  </div>
                </div>

                <div>
                  <div className="flex justify-between text-xs text-gray-500 mb-2">
                    <span>进度</span>
                    <span>
                      {objectiveTask.completed}/{objectiveTask.total}
                    </span>
                  </div>
                  <div className="h-2 rounded-full bg-gray-800 overflow-hidden">
                    <div
                      className="h-full bg-indigo-500 transition-all"
                      style={{ width: pct(objectiveProgress) }}
                    />
                  </div>
                </div>

                {objectiveTask.current_question &&
                  objectiveTask.status === "running" && (
                    <div className="text-xs text-gray-400 bg-gray-900 border border-gray-800 rounded-xl p-3">
                      正在作答：{objectiveTask.current_question}
                    </div>
                  )}

                {objectiveTask.summary && (
                  <div className="rounded-xl bg-gray-900 border border-gray-800 p-4 text-sm text-gray-300 space-y-1">
                    <div>总题数：{objectiveTask.summary.total}</div>
                    <div>选择题：{objectiveTask.summary.choice_count}</div>
                    <div>判断题：{objectiveTask.summary.judge_count}</div>
                  </div>
                )}

                {objectiveTask.status === "completed" && (
                  <button
                    type="button"
                    onClick={downloadObjectiveCsv}
                    className="flex items-center gap-2 px-4 h-10 rounded-lg bg-emerald-700 text-white hover:bg-emerald-600"
                  >
                    <Download size={15} />
                    导出预测结果 CSV
                  </button>
                )}
              </>
            )}
          </section>
        </div>

        {objectiveTask && (
          <div className="overflow-auto rounded-2xl border border-gray-800">
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
                {objectiveRows.map((row) => (
                  <tr
                    key={`${row.display_no}-${row.question}`}
                    className="border-t border-gray-800 align-top"
                  >
                    <td className="px-4 py-3 text-gray-500">
                      {row.display_no}
                    </td>
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
                {objectiveRows.length === 0 && (
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

      <section className="bg-gray-900 border border-gray-800 rounded-2xl p-5 space-y-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0">
            <div className="text-white font-medium">检索 Harness</div>
            <div className="text-sm text-gray-500 mt-1">
              上传 `.jsonl/.csv` 标注集，直接评估检索命中率、平均召回率和
              MRR，不经过答案生成。
            </div>
          </div>
          {retrievalTask && (
            <button
              type="button"
              onClick={() => loadRetrievalTask(retrievalTask.task_id)}
              className="inline-flex items-center justify-center gap-2 px-3 h-9 rounded-lg border border-gray-700 text-gray-300 hover:text-white hover:border-gray-500 transition-colors self-start sm:self-auto w-full sm:w-auto"
            >
              <RefreshCw size={14} />
              刷新状态
            </button>
          )}
        </div>

        <div className="grid lg:grid-cols-[1.3fr_1fr] gap-6">
          <section className="rounded-2xl border border-gray-800 bg-gray-950 p-5 space-y-4">
            <label className="block">
              <div className="text-xs text-gray-500 mb-2">检索评测文件</div>
              <input
                type="file"
                accept=".jsonl,.csv"
                onChange={(e) => setRetrievalFile(e.target.files?.[0] ?? null)}
                className="block w-full text-sm text-gray-300 file:mr-4 file:px-3 file:py-2 file:rounded-lg file:border-0 file:bg-indigo-600 file:text-white hover:file:bg-indigo-500"
              />
            </label>

            <div className="grid md:grid-cols-2 gap-4">
              <label className="block">
                <div className="text-xs text-gray-500 mb-2">检索策略</div>
                <select
                  value={retrievalStrategy}
                  onChange={(e) =>
                    setRetrievalStrategy(e.target.value as RetrievalStrategy)
                  }
                  className="w-full h-10 rounded-lg bg-gray-900 border border-gray-800 px-3 text-sm text-gray-200"
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
                  onChange={(e) => setTopK(Number(e.target.value || 5))}
                  className="w-full h-10 rounded-lg bg-gray-900 border border-gray-800 px-3 text-sm text-gray-200"
                />
              </label>
            </div>

            <div className="rounded-xl border border-gray-800 bg-gray-900 p-4 text-sm text-gray-400 space-y-1">
              <div>
                支持字段：`question/问题`、`gold_chunk_ids`、`gold_doc_ids`、`domain/专业`。
              </div>
              <div>
                当同时给 `gold_chunk_ids` 和 `gold_doc_ids` 时，默认按 chunk
                命中判定。
              </div>
            </div>

            <button
              type="button"
              onClick={handleStartRetrieval}
              disabled={retrievalStarting}
              className="flex items-center gap-2 px-4 h-10 rounded-lg bg-indigo-600 text-white hover:bg-indigo-500 disabled:opacity-50"
            >
              {retrievalStarting ? (
                <Loader2 size={15} className="animate-spin" />
              ) : (
                <Play size={15} />
              )}
              开始检索评测
            </button>
          </section>

          <section className="rounded-2xl border border-gray-800 bg-gray-950 p-5 space-y-4">
            {!retrievalTask && (
              <div className="text-sm text-gray-500">
                尚未启动检索评测任务。
              </div>
            )}
            {retrievalTask && (
              <>
                <div className="grid grid-cols-2 gap-3">
                  <div className="rounded-xl bg-gray-900 border border-gray-800 p-4">
                    <div className="text-xs text-gray-500">任务状态</div>
                    <div className="mt-1 text-sm text-white">
                      {retrievalTask.status}
                    </div>
                  </div>
                  <div className="rounded-xl bg-gray-900 border border-gray-800 p-4">
                    <div className="text-xs text-gray-500">命中数</div>
                    <div className="mt-1 text-lg text-emerald-400">
                      {retrievalTask.matched}
                    </div>
                  </div>
                </div>

                <div>
                  <div className="flex justify-between text-xs text-gray-500 mb-2">
                    <span>进度</span>
                    <span>
                      {retrievalTask.completed}/{retrievalTask.total}
                    </span>
                  </div>
                  <div className="h-2 rounded-full bg-gray-800 overflow-hidden">
                    <div
                      className="h-full bg-indigo-500 transition-all"
                      style={{ width: pct(retrievalProgress) }}
                    />
                  </div>
                </div>

                {retrievalTask.current_question &&
                  retrievalTask.status === "running" && (
                    <div className="text-xs text-gray-400 bg-gray-900 border border-gray-800 rounded-xl p-3">
                      正在检索：{retrievalTask.current_question}
                    </div>
                  )}

                {retrievalTask.summary && (
                  <div className="rounded-xl bg-gray-900 border border-gray-800 p-4 text-sm text-gray-300 space-y-1">
                    <div>Hit Rate：{pct(retrievalTask.summary.hit_rate)}</div>
                    <div>
                      Avg Recall：{retrievalTask.summary.avg_recall.toFixed(4)}
                    </div>
                    <div>MRR：{retrievalTask.summary.mrr.toFixed(4)}</div>
                    <div>
                      Chunk 标注：{retrievalTask.summary.chunk_target_count}
                    </div>
                    <div>
                      Doc 标注：{retrievalTask.summary.doc_target_count}
                    </div>
                  </div>
                )}

                {retrievalTask.status === "completed" && (
                  <button
                    type="button"
                    onClick={downloadRetrievalCsv}
                    className="flex items-center gap-2 px-4 h-10 rounded-lg bg-emerald-700 text-white hover:bg-emerald-600"
                  >
                    <Download size={15} />
                    导出检索结果 CSV
                  </button>
                )}
              </>
            )}
          </section>
        </div>

        {retrievalTask && (
          <div className="overflow-auto rounded-2xl border border-gray-800">
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
                {retrievalRows.map((row) => (
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
                    <td className="px-4 py-3 text-gray-400">
                      {row.target_type}
                    </td>
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
                {retrievalRows.length === 0 && (
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
    </div>
  );
}
