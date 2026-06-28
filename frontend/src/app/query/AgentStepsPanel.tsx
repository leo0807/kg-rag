"use client";

import { Brain, Check, ChevronDown, ChevronUp, Database, Edit3, Loader2, Search, X, Zap } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { AgentStepInfo } from "./types";

interface Props {
  steps: AgentStepInfo[];
  streaming?: boolean;
}

function getStepMeta(action: string): { icon: React.ReactNode; color: string } {
  const a = action.toLowerCase();
  if (a.includes("检索") || a.includes("search") || a.includes("retrieve") || a.includes("查询"))
    return { icon: <Search size={10} />, color: "text-indigo-400 bg-indigo-500/10 border-indigo-500/30" };
  if (a.includes("分析") || a.includes("analyz") || a.includes("reason") || a.includes("推理") || a.includes("思考"))
    return { icon: <Brain size={10} />, color: "text-violet-400 bg-violet-500/10 border-violet-500/30" };
  if (a.includes("生成") || a.includes("generat") || a.includes("write") || a.includes("回答") || a.includes("answer"))
    return { icon: <Edit3 size={10} />, color: "text-sky-400 bg-sky-500/10 border-sky-500/30" };
  if (a.includes("知识") || a.includes("graph") || a.includes("图谱") || a.includes("entity") || a.includes("实体"))
    return { icon: <Database size={10} />, color: "text-teal-400 bg-teal-500/10 border-teal-500/30" };
  return { icon: <Zap size={10} />, color: "text-amber-400 bg-amber-500/10 border-amber-500/30" };
}

function statusDot(status: AgentStepInfo["status"]) {
  if (status === "done")   return "bg-emerald-500/80 border-emerald-400/40 shadow-[0_0_6px_rgba(52,211,153,0.4)]";
  if (status === "failed") return "bg-rose-500/80    border-rose-400/40    shadow-[0_0_6px_rgba(244,63,94,0.4)]";
  return "bg-cyan-500/80 border-cyan-400/50 animate-pulse shadow-[0_0_8px_rgba(34,211,238,0.5)]";
}

export function AgentStepsPanel({ steps, streaming }: Props) {
  const [open, setOpen] = useState(Boolean(streaming));

  useEffect(() => { if (streaming) setOpen(true); }, [streaming]);

  const summary = useMemo(() => {
    const running = steps.find(s => s.status === "running");
    if (running) return running.action;
    return steps[steps.length - 1]?.action ?? "";
  }, [steps]);

  const doneCount = steps.filter(s => s.status === "done").length;
  const progress  = steps.length > 0 ? (doneCount / steps.length) * 100 : 0;

  return (
    <div className="mb-3 rounded-xl border border-slate-700/40 bg-slate-950/90 overflow-hidden"
      style={{ animation: "scale-fade 0.3s ease both" }}>

      {/* ── Header ── */}
      <button type="button" onClick={() => setOpen(v => !v)}
        className="flex w-full items-center gap-2.5 px-3 py-2.5 hover:bg-white/3 transition-colors text-left">

        {/* Spinner / done indicator */}
        <div className="relative shrink-0 w-4 h-4 flex items-center justify-center">
          {streaming ? (
            <>
              <Loader2 size={14} className="animate-spin text-cyan-400" />
              <span className="absolute inset-0 rounded-full bg-cyan-400/15 animate-ping" style={{ animationDuration: "1.8s" }} />
            </>
          ) : (
            <div className={`w-3 h-3 rounded-full border ${doneCount === steps.length && steps.length > 0 ? "bg-emerald-500 border-emerald-400/40" : "bg-slate-600 border-slate-500/40"}`} />
          )}
        </div>

        <span className="text-xs font-semibold text-slate-200">Agent 推理链路</span>

        {/* Progress bar */}
        {steps.length > 0 && (
          <div className="flex items-center gap-1.5 flex-1 max-w-[120px]">
            <div className="flex-1 h-1 bg-slate-800 rounded-full overflow-hidden">
              <div className="h-full bg-gradient-to-r from-cyan-500 to-blue-500 rounded-full transition-all duration-700"
                style={{ width: `${progress}%` }} />
            </div>
            <span className="text-[10px] text-slate-500 tabular-nums shrink-0">{doneCount}/{steps.length}</span>
          </div>
        )}

        {summary && (
          <span className="text-[10px] text-slate-500 ml-auto mr-1 truncate max-w-[140px] hidden sm:block">{summary}</span>
        )}
        {open ? <ChevronUp size={12} className="text-slate-500 shrink-0" /> : <ChevronDown size={12} className="text-slate-500 shrink-0" />}
      </button>

      {/* ── Timeline ── */}
      {open && steps.length > 0 && (
        <div className="px-3 pb-3 pt-0.5">
          <div className="relative pl-6">
            {steps.map((step, idx) => {
              const meta = getStepMeta(step.action);
              const isLast = idx === steps.length - 1;
              return (
                <div key={`${step.step}-${step.action}`} className="relative"
                  style={{ animation: `slide-in-left 0.35s ease both ${idx * 65}ms` }}>

                  {/* Vertical connector */}
                  {!isLast && (
                    <div className={`absolute left-[-13px] top-[22px] bottom-0 w-px transition-colors duration-500 ${
                      step.status === "done" ? "bg-emerald-500/25" : "bg-slate-700/60"
                    }`} />
                  )}

                  {/* Status dot */}
                  <div className={`absolute left-[-17px] top-[7px] w-[14px] h-[14px] rounded-full border flex items-center justify-center ${statusDot(step.status)}`}>
                    {step.status === "done"   && <Check size={8} className="text-white" />}
                    {step.status === "failed" && <X    size={8} className="text-white" />}
                  </div>

                  {/* Step card */}
                  <div className={`mb-2 ml-1.5 rounded-lg border px-3 py-2 ${
                    step.status === "running"
                      ? "border-cyan-500/20 bg-cyan-500/5"
                      : step.status === "failed"
                      ? "border-rose-700/30 bg-rose-950/20"
                      : "border-slate-800/70 bg-slate-900/50"
                  }`}>
                    <div className="flex items-center gap-2">
                      {/* Step type badge */}
                      <span className={`inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded border font-medium ${meta.color}`}>
                        {meta.icon}
                      </span>
                      <span className="text-xs text-slate-200 font-medium leading-tight">{step.action}</span>
                      {step.status === "running" && (
                        <span className="ml-auto text-[10px] text-cyan-400/80 animate-pulse shrink-0">执行中</span>
                      )}
                    </div>

                    {step.result_summary && (
                      <p className="mt-1.5 text-[11px] text-slate-400 leading-relaxed pl-3 border-l-2 border-slate-700/60 ml-0.5">
                        {step.result_summary}
                      </p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
