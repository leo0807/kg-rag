"use client";

import { Check, ChevronDown, ChevronUp, Loader2, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { AgentStepInfo } from "./types";

interface Props {
  steps: AgentStepInfo[];
  streaming?: boolean;
}

function statusIcon(status: AgentStepInfo["status"]) {
  if (status === "done") {
    return <Check size={12} className="text-emerald-400" />;
  }
  if (status === "failed") return <X size={12} className="text-rose-400" />;
  return <Loader2 size={12} className="animate-spin text-amber-400" />;
}

export function AgentStepsPanel({ steps, streaming }: Props) {
  const [open, setOpen] = useState(Boolean(streaming));

  useEffect(() => {
    setOpen(Boolean(streaming));
  }, [streaming]);

  const summary = useMemo(() => {
    const running = steps.find((step) => step.status === "running");
    if (running) return running.action;
    const last = steps[steps.length - 1];
    return last?.action || "Agent 执行过程";
  }, [steps]);

  return (
    <div className="mb-3 rounded-xl border border-slate-700/70 bg-slate-950/80 px-3 py-2">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-3 text-left text-xs text-slate-300"
      >
        <span className="flex items-center gap-2">
          <Loader2
            size={12}
            className={streaming ? "animate-spin text-sky-400" : "text-sky-400"}
          />
          <span>Agent 执行过程</span>
          <span className="text-slate-500">· {summary}</span>
        </span>
        {open ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
      </button>

      {open && (
        <div className="mt-3 space-y-2">
          {steps.map((step) => (
            <div
              key={`${step.step}-${step.action}`}
              className="rounded-lg border border-slate-800 bg-slate-900/70 px-3 py-2"
            >
              <div className="flex items-center gap-2 text-xs text-slate-200">
                {statusIcon(step.status)}
                <span className="font-medium">Step {step.step}:</span>
                <span>{step.action}</span>
              </div>
              {step.result_summary && (
                <div className="mt-1 pl-5 text-[11px] text-slate-400">
                  → {step.result_summary}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
