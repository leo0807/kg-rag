"use client";

import { Activity, Bot, BrainCircuit, FileSearch, Play, RefreshCw, Shield, Wrench } from "lucide-react";
import { useMemo, useState } from "react";
import { useOpsData } from "./useOpsData";
import { OpsHarnessTab } from "./OpsHarnessTab";
import { OpsBaselineTab } from "./OpsBaselineTab";

function statusTone(status: string) {
  if (status === "running") return "bg-indigo-500/10 text-indigo-300";
  if (status === "completed") return "bg-emerald-500/10 text-emerald-300";
  if (status === "failed") return "bg-red-500/10 text-red-300";
  if (status === "queued") return "bg-amber-500/10 text-amber-300";
  return "bg-gray-800 text-gray-300";
}

function pct(value: number) { return `${(value * 100).toFixed(1)}%`; }

export default function AdminOpsPage() {
  const { overview, runtimeItems, loading, refreshing, error, loadOverview, refresh, pollRef } = useOpsData();
  const [workspaceTab, setWorkspaceTab] = useState<"harness" | "baseline">("harness");

  const cards = useMemo(
    () => overview ? [
      { label: "知识规模", value: overview.knowledge.documents, sub: `${overview.knowledge.sections} 章节 / ${overview.knowledge.drawings} 图纸`, Icon: BrainCircuit },
      { label: "多模态资产", value: overview.knowledge.images, sub: `${overview.quality.retrieval_cases} 条内置检索 case`, Icon: FileSearch },
      { label: "运行任务", value: overview.runtime.running, sub: `${overview.runtime.total} 个可见任务`, Icon: Activity },
      { label: "审计事件(7d)", value: overview.quality.audit_events_7d, sub: `${overview.quality.negative_feedback_7d} 条负反馈`, Icon: Shield },
    ] : [],
    [overview],
  );

  return (
    <div className="flex-1 overflow-auto bg-gray-950 p-6">
      <div className="mx-auto max-w-7xl space-y-6">
        <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <h1 className="flex items-center gap-3 text-2xl font-semibold text-white"><Bot className="text-indigo-400" />AI 工程台</h1>
            <p className="mt-1 text-sm text-gray-500">统一 harness、回归评测、任务运行时与审计视图，作为第一批工程化入口。</p>
          </div>
          <button type="button" onClick={refresh} disabled={refreshing} className="inline-flex items-center gap-2 rounded-xl border border-gray-800 bg-gray-900 px-4 py-2 text-sm text-gray-200 hover:bg-gray-800 disabled:opacity-50">
            <RefreshCw size={14} className={refreshing ? "animate-spin" : ""} />刷新工程台
          </button>
        </div>

        {error && <div className="rounded-2xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-200">{error}</div>}

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
          {cards.map(({ label, value, sub, Icon }) => (
            <div key={label} className="rounded-2xl border border-gray-800 bg-gray-900 p-5 shadow-xl">
              <div className="mb-4 flex items-center justify-between">
                <div className="rounded-xl bg-indigo-500/10 p-2"><Icon size={18} className="text-indigo-300" /></div>
                <div className="text-[10px] uppercase tracking-[0.2em] text-gray-600">ops</div>
              </div>
              <div className="text-xs uppercase tracking-[0.2em] text-gray-500">{label}</div>
              <div className="mt-2 text-3xl font-semibold text-white">{value}</div>
              <div className="mt-1 text-xs text-gray-500">{sub}</div>
            </div>
          ))}
        </div>

        <section className="rounded-3xl border border-gray-800 bg-gray-900 p-6 shadow-xl">
          <div className="mb-5 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-white">工程入口</h2>
              <p className="text-xs text-gray-500">先选择要做的事，再进入对应的调度与验证流程。</p>
            </div>
            <div className="inline-flex rounded-2xl border border-gray-800 bg-gray-950 p-1">
              {([
                { key: "harness" as const, label: "Harness 调度台", Icon: Wrench },
                { key: "baseline" as const, label: "检索基线回归", Icon: Play },
              ]).map(({ key, label, Icon }) => (
                <button key={key} type="button" onClick={() => setWorkspaceTab(key)}
                  className={`inline-flex items-center gap-2 rounded-xl px-4 py-2 text-sm transition-colors ${workspaceTab === key ? "bg-indigo-600 text-white" : "text-gray-400 hover:bg-gray-900 hover:text-white"}`}>
                  <Icon size={15} />{label}
                </button>
              ))}
            </div>
          </div>
          {workspaceTab === "harness" ? (
            <OpsHarnessTab onAfterRun={loadOverview} />
          ) : (
            <OpsBaselineTab pollRef={pollRef} onAfterRun={loadOverview} />
          )}
        </section>

        <section className="rounded-3xl border border-gray-800 bg-gray-900 p-6 shadow-xl">
          <div className="mb-4 flex items-center gap-3">
            <div className="rounded-xl bg-amber-500/10 p-2"><Activity size={18} className="text-amber-300" /></div>
            <div>
              <h2 className="text-lg font-semibold text-white">统一任务运行时</h2>
              <p className="text-xs text-gray-500">汇总入库、重处理、评测三类后台任务，不再分散看。</p>
            </div>
          </div>
          <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
            {runtimeItems.map((item) => (
              <div key={`${item.source}-${item.task_id}`} className="rounded-2xl border border-gray-800 bg-gray-950/60 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-sm font-medium text-white">{item.label}</div>
                    <div className="text-xs text-gray-500">{item.source} · {item.task_id}</div>
                  </div>
                  <span className={`rounded-full px-2.5 py-1 text-[10px] uppercase tracking-widest ${statusTone(item.status)}`}>{item.status}</span>
                </div>
                <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-gray-900">
                  <div className="h-full rounded-full bg-indigo-500" style={{ width: `${Math.round(item.progress * 100)}%` }} />
                </div>
                <div className="mt-3 flex flex-wrap gap-3 text-xs text-gray-400">
                  <span>进度 {pct(item.progress)}</span>
                  {item.current && <span>当前 {item.current}</span>}
                </div>
                {item.message && <div className="mt-2 text-sm text-gray-500">{item.message}</div>}
              </div>
            ))}
            {runtimeItems.length === 0 && !loading && (
              <div className="rounded-2xl border border-dashed border-gray-800 px-4 py-6 text-sm text-gray-500">当前没有可见的后台任务。</div>
            )}
          </div>
        </section>

        <section className="rounded-3xl border border-gray-800 bg-gray-900 p-6 shadow-xl">
          <div className="mb-4 flex items-center gap-3">
            <div className="rounded-xl bg-sky-500/10 p-2"><Shield size={18} className="text-sky-300" /></div>
            <div>
              <h2 className="text-lg font-semibold text-white">最近审计轨迹</h2>
              <p className="text-xs text-gray-500">这里会看到 harness 调用、回归触发等关键管理动作。</p>
            </div>
          </div>
          <div className="overflow-hidden rounded-2xl border border-gray-800">
            <table className="w-full text-left text-sm">
              <thead className="bg-gray-950/70 text-xs uppercase tracking-[0.2em] text-gray-500">
                <tr><th className="px-4 py-3">时间</th><th className="px-4 py-3">用户</th><th className="px-4 py-3">动作</th><th className="px-4 py-3">详情</th></tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {overview?.recent_audits.map((audit) => (
                  <tr key={audit.id} className="bg-gray-900/40">
                    <td className="px-4 py-3 text-xs text-gray-500">{new Date(audit.created_at).toLocaleString()}</td>
                    <td className="px-4 py-3 text-sm text-gray-200">{audit.username}</td>
                    <td className="px-4 py-3 text-sm text-indigo-300">{audit.action}</td>
                    <td className="px-4 py-3 text-sm text-gray-400">{audit.detail}</td>
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
