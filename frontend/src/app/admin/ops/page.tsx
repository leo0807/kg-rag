"use client";

import {
  Activity,
  Bot,
  BrainCircuit,
  FileSearch,
  Loader2,
  Play,
  RefreshCw,
  Shield,
  Wrench,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { fetchApi } from "@/lib/api";

interface Overview {
  knowledge: {
    documents: number;
    sections: number;
    images: number;
    drawings: number;
  };
  quality: {
    retrieval_cases: number;
    negative_feedback_7d: number;
    audit_events_7d: number;
  };
  runtime: {
    total: number;
    running: number;
    failed: number;
    queued: number;
    completed: number;
  };
  recent_audits: {
    id: number;
    action: string;
    resource: string;
    detail: string;
    username: string;
    created_at: string;
  }[];
}

interface RuntimeItem {
  source: string;
  task_type: string;
  task_id: string;
  label: string;
  status: string;
  progress: number;
  total: number;
  completed: number;
  current: string;
  message: string;
  updated_at: string;
}

interface HarnessResult {
  question: string;
  answer: string;
  plan: {
    strategy: string;
    reason: string;
    doc_id: string;
    intents: string[];
    steps: { tool: string; description: string }[];
  };
  runtime: {
    strategy: string;
    top_k: number;
    section_hits: number;
    image_hits: number;
    drawing_only: boolean;
    warnings: string[];
    retrieval_trace_counts: Record<string, number>;
  };
  section_sources: {
    chunk_id: string;
    doc_id: string;
    number: string;
    title: string;
    score: number;
    retrieval_trace: string[];
    source_type: string[];
    content: string;
  }[];
  image_sources: {
    image_id: string;
    doc_id: string;
    summary: string;
    caption: string;
    is_drawing: boolean;
    section_number?: string;
    section_title?: string;
    keyword_hits: number;
    url?: string | null;
  }[];
}

interface RetrievalBaselineTask {
  task_id: string;
  filename: string;
  status: "queued" | "running" | "completed" | "failed";
  total: number;
  completed: number;
  matched: number;
  unmatched: number;
  current_question: string;
  summary: {
    total: number;
    matched: number;
    unmatched: number;
    hit_rate: number;
    avg_recall: number;
    mrr: number;
  } | null;
  error: string;
}

function pct(value: number) {
  return `${(value * 100).toFixed(1)}%`;
}

function statusTone(status: string) {
  if (status === "running") return "bg-indigo-500/10 text-indigo-300";
  if (status === "completed") return "bg-emerald-500/10 text-emerald-300";
  if (status === "failed") return "bg-red-500/10 text-red-300";
  if (status === "queued") return "bg-amber-500/10 text-amber-300";
  return "bg-gray-800 text-gray-300";
}

export default function AdminOpsPage() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [runtimeItems, setRuntimeItems] = useState<RuntimeItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const [question, setQuestion] = useState("CPS1000 的工程图纸主要讲了什么？");
  const [docId, setDocId] = useState("CPS1000");
  const [topK, setTopK] = useState(5);
  const [harnessLoading, setHarnessLoading] = useState(false);
  const [harnessResult, setHarnessResult] = useState<HarnessResult | null>(
    null,
  );

  const [baselineTask, setBaselineTask] =
    useState<RetrievalBaselineTask | null>(null);
  const [baselineLoading, setBaselineLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);

  const loadOverview = useCallback(async () => {
    const [overviewData, runtimeData] = await Promise.all([
      fetchApi<Overview>("/api/admin/ops/overview"),
      fetchApi<{ items: RuntimeItem[] }>("/api/admin/ops/runtime?limit=12"),
    ]);
    setOverview(overviewData);
    setRuntimeItems(runtimeData.items);
  }, []);

  const refresh = useCallback(async () => {
    try {
      setRefreshing(true);
      setError(null);
      await loadOverview();
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载工程台失败");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [loadOverview]);

  useEffect(() => {
    refresh();
    const timer = window.setInterval(refresh, 10000);
    return () => {
      window.clearInterval(timer);
      if (pollRef.current) {
        window.clearInterval(pollRef.current);
      }
    };
  }, [refresh]);

  async function runHarness() {
    try {
      setHarnessLoading(true);
      setError(null);
      const data = await fetchApi<HarnessResult>(
        "/api/admin/ops/harness/query",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            question,
            doc_id: docId.trim(),
            top_k: topK,
          }),
        },
      );
      setHarnessResult(data);
      await loadOverview();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Harness 执行失败");
    } finally {
      setHarnessLoading(false);
    }
  }

  async function pollBaseline(taskId: string) {
    const data = await fetchApi<RetrievalBaselineTask>(
      `/api/admin/ops/retrieval-baseline/${taskId}`,
    );
    setBaselineTask(data);
    if (data.status === "completed" || data.status === "failed") {
      if (pollRef.current) {
        window.clearInterval(pollRef.current);
        pollRef.current = null;
      }
      await loadOverview();
    }
  }

  async function runBaseline() {
    try {
      setBaselineLoading(true);
      setError(null);
      const data = await fetchApi<RetrievalBaselineTask>(
        "/api/admin/ops/retrieval-baseline/run",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ strategy: "parallel", top_k: 5 }),
        },
      );
      setBaselineTask(data);
      if (pollRef.current) {
        window.clearInterval(pollRef.current);
      }
      pollRef.current = window.setInterval(() => {
        pollBaseline(data.task_id);
      }, 1500);
    } catch (err) {
      setError(err instanceof Error ? err.message : "基线回归启动失败");
    } finally {
      setBaselineLoading(false);
    }
  }

  const cards = useMemo(
    () =>
      overview
        ? [
            {
              label: "知识规模",
              value: overview.knowledge.documents,
              sub: `${overview.knowledge.sections} 章节 / ${overview.knowledge.drawings} 图纸`,
              Icon: BrainCircuit,
            },
            {
              label: "多模态资产",
              value: overview.knowledge.images,
              sub: `${overview.quality.retrieval_cases} 条内置检索 case`,
              Icon: FileSearch,
            },
            {
              label: "运行任务",
              value: overview.runtime.running,
              sub: `${overview.runtime.total} 个可见任务`,
              Icon: Activity,
            },
            {
              label: "审计事件(7d)",
              value: overview.quality.audit_events_7d,
              sub: `${overview.quality.negative_feedback_7d} 条负反馈`,
              Icon: Shield,
            },
          ]
        : [],
    [overview],
  );

  return (
    <div className="flex-1 overflow-auto bg-gray-950 p-6">
      <div className="mx-auto max-w-7xl space-y-6">
        <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <h1 className="flex items-center gap-3 text-2xl font-semibold text-white">
              <Bot className="text-indigo-400" />
              AI 工程台
            </h1>
            <p className="mt-1 text-sm text-gray-500">
              统一
              harness、回归评测、任务运行时与审计视图，作为第一批工程化入口。
            </p>
          </div>
          <button
            type="button"
            onClick={refresh}
            disabled={refreshing}
            className="inline-flex items-center gap-2 rounded-xl border border-gray-800 bg-gray-900 px-4 py-2 text-sm text-gray-200 hover:bg-gray-800 disabled:opacity-50"
          >
            <RefreshCw size={14} className={refreshing ? "animate-spin" : ""} />
            刷新工程台
          </button>
        </div>

        {error && (
          <div className="rounded-2xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-200">
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
          {cards.map(({ label, value, sub, Icon }) => (
            <div
              key={label}
              className="rounded-2xl border border-gray-800 bg-gray-900 p-5 shadow-xl"
            >
              <div className="mb-4 flex items-center justify-between">
                <div className="rounded-xl bg-indigo-500/10 p-2">
                  <Icon size={18} className="text-indigo-300" />
                </div>
                <div className="text-[10px] uppercase tracking-[0.2em] text-gray-600">
                  ops
                </div>
              </div>
              <div className="text-xs uppercase tracking-[0.2em] text-gray-500">
                {label}
              </div>
              <div className="mt-2 text-3xl font-semibold text-white">
                {value}
              </div>
              <div className="mt-1 text-xs text-gray-500">{sub}</div>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1.35fr_0.95fr]">
          <section className="rounded-3xl border border-gray-800 bg-gray-900 p-6 shadow-xl">
            <div className="mb-5 flex items-center gap-3">
              <div className="rounded-xl bg-indigo-500/10 p-2">
                <Wrench size={18} className="text-indigo-300" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-white">
                  Harness 调度台
                </h2>
                <p className="text-xs text-gray-500">
                  自动规划策略，并把章节证据和图纸证据一起拉平展示。
                </p>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-3 md:grid-cols-[1fr_180px_110px]">
              <textarea
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                rows={3}
                className="rounded-2xl border border-gray-800 bg-gray-950 px-4 py-3 text-sm text-gray-100 outline-none ring-0 placeholder:text-gray-600"
                placeholder="输入一个复杂问题，例如 CPS1000 的工程图纸主要讲了什么？"
              />
              <input
                value={docId}
                onChange={(event) => setDocId(event.target.value)}
                className="rounded-2xl border border-gray-800 bg-gray-950 px-4 py-3 text-sm text-gray-100 outline-none placeholder:text-gray-600"
                placeholder="限定文档，可空"
              />
              <div className="flex gap-3">
                <input
                  type="number"
                  min={1}
                  max={10}
                  value={topK}
                  onChange={(event) => setTopK(Number(event.target.value || 5))}
                  className="w-full rounded-2xl border border-gray-800 bg-gray-950 px-4 py-3 text-sm text-gray-100 outline-none"
                />
                <button
                  type="button"
                  onClick={runHarness}
                  disabled={harnessLoading || !question.trim()}
                  className="inline-flex items-center justify-center rounded-2xl bg-indigo-600 px-4 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
                >
                  {harnessLoading ? (
                    <Loader2 size={16} className="animate-spin" />
                  ) : (
                    "运行"
                  )}
                </button>
              </div>
            </div>

            {harnessResult && (
              <div className="mt-6 space-y-4">
                <div className="rounded-2xl border border-indigo-500/20 bg-indigo-500/10 p-4">
                  <div className="flex flex-wrap items-center gap-2 text-xs">
                    <span className="rounded-full bg-indigo-500/20 px-2 py-1 text-indigo-200">
                      {harnessResult.plan.strategy}
                    </span>
                    {harnessResult.plan.intents.map((intent) => (
                      <span
                        key={intent}
                        className="rounded-full bg-gray-800 px-2 py-1 text-gray-300"
                      >
                        {intent}
                      </span>
                    ))}
                  </div>
                  <div className="mt-3 text-sm text-gray-200">
                    {harnessResult.plan.reason}
                  </div>
                  <div className="mt-3 rounded-xl bg-gray-950/70 p-4 text-sm leading-7 text-gray-100">
                    {harnessResult.answer}
                  </div>
                </div>

                <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                  <div className="rounded-2xl border border-gray-800 bg-gray-950/50 p-4">
                    <div className="mb-3 text-xs uppercase tracking-[0.2em] text-gray-500">
                      章节证据 {harnessResult.runtime.section_hits}
                    </div>
                    <div className="space-y-3">
                      {harnessResult.section_sources
                        .slice(0, 5)
                        .map((section) => (
                          <div
                            key={section.chunk_id}
                            className="rounded-xl border border-gray-800 bg-gray-900/70 p-3"
                          >
                            <div className="text-sm font-medium text-white">
                              {section.doc_id} §{section.number} {section.title}
                            </div>
                            <div className="mt-1 text-xs text-gray-500">
                              score {section.score} ·{" "}
                              {section.retrieval_trace.join(" / ") ||
                                "no-trace"}
                            </div>
                            <div className="mt-2 line-clamp-4 text-sm leading-6 text-gray-300">
                              {section.content}
                            </div>
                          </div>
                        ))}
                    </div>
                  </div>

                  <div className="rounded-2xl border border-gray-800 bg-gray-950/50 p-4">
                    <div className="mb-3 text-xs uppercase tracking-[0.2em] text-gray-500">
                      图片/图纸证据 {harnessResult.runtime.image_hits}
                    </div>
                    <div className="space-y-3">
                      {harnessResult.image_sources.length === 0 && (
                        <div className="rounded-xl border border-dashed border-gray-800 px-4 py-6 text-sm text-gray-500">
                          当前问题没有补充到额外图片证据。
                        </div>
                      )}
                      {harnessResult.image_sources.map((image) => (
                        <div
                          key={image.image_id}
                          className="rounded-xl border border-gray-800 bg-gray-900/70 p-3"
                        >
                          <div className="flex items-center justify-between gap-3">
                            <div className="text-sm font-medium text-white">
                              {image.doc_id} #{image.image_id}
                            </div>
                            <span
                              className={`rounded-full px-2 py-1 text-[10px] uppercase tracking-widest ${
                                image.is_drawing
                                  ? "bg-emerald-500/10 text-emerald-300"
                                  : "bg-gray-800 text-gray-300"
                              }`}
                            >
                              {image.is_drawing ? "drawing" : "image"}
                            </span>
                          </div>
                          <div className="mt-2 text-sm leading-6 text-gray-300">
                            {image.summary || image.caption || "暂无摘要"}
                          </div>
                          <div className="mt-2 text-xs text-gray-500">
                            关键词命中 {image.keyword_hits}
                            {image.section_number
                              ? ` · 章节 ${image.section_number}`
                              : ""}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </section>

          <section className="space-y-6">
            <div className="rounded-3xl border border-gray-800 bg-gray-900 p-6 shadow-xl">
              <div className="mb-4 flex items-center gap-3">
                <div className="rounded-xl bg-emerald-500/10 p-2">
                  <Play size={18} className="text-emerald-300" />
                </div>
                <div>
                  <h2 className="text-lg font-semibold text-white">
                    检索基线回归
                  </h2>
                  <p className="text-xs text-gray-500">
                    直接运行仓库内置 `retrieval_cases.jsonl`，做最小回归。
                  </p>
                </div>
              </div>

              <button
                type="button"
                onClick={runBaseline}
                disabled={baselineLoading}
                className="inline-flex items-center gap-2 rounded-2xl bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
              >
                {baselineLoading ? (
                  <Loader2 size={15} className="animate-spin" />
                ) : (
                  <Play size={15} />
                )}
                运行内置回归
              </button>

              <div className="mt-4 rounded-2xl border border-gray-800 bg-gray-950/60 p-4">
                {!baselineTask && (
                  <div className="text-sm text-gray-500">
                    还没有启动本轮基线回归。
                  </div>
                )}
                {baselineTask && (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <div className="text-sm font-medium text-white">
                          {baselineTask.filename}
                        </div>
                        <div className="text-xs text-gray-500">
                          task: {baselineTask.task_id}
                        </div>
                      </div>
                      <span
                        className={`rounded-full px-2.5 py-1 text-[10px] uppercase tracking-widest ${statusTone(
                          baselineTask.status,
                        )}`}
                      >
                        {baselineTask.status}
                      </span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-gray-900">
                      <div
                        className="h-full rounded-full bg-emerald-500 transition-all"
                        style={{
                          width: `${Math.round(
                            (baselineTask.completed /
                              Math.max(baselineTask.total, 1)) *
                              100,
                          )}%`,
                        }}
                      />
                    </div>
                    <div className="flex flex-wrap gap-4 text-xs text-gray-400">
                      <span>
                        进度 {baselineTask.completed}/{baselineTask.total}
                      </span>
                      {baselineTask.summary && (
                        <>
                          <span>
                            命中率 {pct(baselineTask.summary.hit_rate)}
                          </span>
                          <span>
                            平均召回 {pct(baselineTask.summary.avg_recall)}
                          </span>
                          <span>MRR {baselineTask.summary.mrr.toFixed(3)}</span>
                        </>
                      )}
                    </div>
                    {baselineTask.current_question &&
                      baselineTask.status === "running" && (
                        <div className="text-sm text-gray-300">
                          当前问题：{baselineTask.current_question}
                        </div>
                      )}
                    {baselineTask.error && (
                      <div className="text-sm text-red-300">
                        {baselineTask.error}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>

            <div className="rounded-3xl border border-gray-800 bg-gray-900 p-6 shadow-xl">
              <div className="mb-4 flex items-center gap-3">
                <div className="rounded-xl bg-amber-500/10 p-2">
                  <Activity size={18} className="text-amber-300" />
                </div>
                <div>
                  <h2 className="text-lg font-semibold text-white">
                    统一任务运行时
                  </h2>
                  <p className="text-xs text-gray-500">
                    汇总入库、重处理、评测三类后台任务，不再分散看。
                  </p>
                </div>
              </div>
              <div className="space-y-3">
                {runtimeItems.map((item) => (
                  <div
                    key={`${item.source}-${item.task_id}`}
                    className="rounded-2xl border border-gray-800 bg-gray-950/60 p-4"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <div className="text-sm font-medium text-white">
                          {item.label}
                        </div>
                        <div className="text-xs text-gray-500">
                          {item.source} · {item.task_id}
                        </div>
                      </div>
                      <span
                        className={`rounded-full px-2.5 py-1 text-[10px] uppercase tracking-widest ${statusTone(
                          item.status,
                        )}`}
                      >
                        {item.status}
                      </span>
                    </div>
                    <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-gray-900">
                      <div
                        className="h-full rounded-full bg-indigo-500"
                        style={{ width: `${Math.round(item.progress * 100)}%` }}
                      />
                    </div>
                    <div className="mt-3 flex flex-wrap gap-3 text-xs text-gray-400">
                      <span>进度 {pct(item.progress)}</span>
                      {item.current && <span>当前 {item.current}</span>}
                    </div>
                    {item.message && (
                      <div className="mt-2 text-sm text-gray-500">
                        {item.message}
                      </div>
                    )}
                  </div>
                ))}
                {runtimeItems.length === 0 && !loading && (
                  <div className="rounded-2xl border border-dashed border-gray-800 px-4 py-6 text-sm text-gray-500">
                    当前没有可见的后台任务。
                  </div>
                )}
              </div>
            </div>
          </section>
        </div>

        <section className="rounded-3xl border border-gray-800 bg-gray-900 p-6 shadow-xl">
          <div className="mb-4 flex items-center gap-3">
            <div className="rounded-xl bg-sky-500/10 p-2">
              <Shield size={18} className="text-sky-300" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">最近审计轨迹</h2>
              <p className="text-xs text-gray-500">
                这里会看到 harness 调用、回归触发等关键管理动作。
              </p>
            </div>
          </div>
          <div className="overflow-hidden rounded-2xl border border-gray-800">
            <table className="w-full text-left text-sm">
              <thead className="bg-gray-950/70 text-xs uppercase tracking-[0.2em] text-gray-500">
                <tr>
                  <th className="px-4 py-3">时间</th>
                  <th className="px-4 py-3">用户</th>
                  <th className="px-4 py-3">动作</th>
                  <th className="px-4 py-3">详情</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {overview?.recent_audits.map((audit) => (
                  <tr key={audit.id} className="bg-gray-900/40">
                    <td className="px-4 py-3 text-xs text-gray-500">
                      {new Date(audit.created_at).toLocaleString()}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-200">
                      {audit.username}
                    </td>
                    <td className="px-4 py-3 text-sm text-indigo-300">
                      {audit.action}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-400">
                      {audit.detail}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </div>
  );
}
