"use client";

import { useState } from "react";

export interface ReasoningStep {
    hop: number;
    query: string;
    found?: number;
    titles?: string[];
    sub_queries?: string[];
}

export function ReasoningChain({ steps }: { steps: ReasoningStep[] }) {
    const [open, setOpen] = useState(true);
    if (!steps.length) return null;
    return (
        <div className="mb-6 border border-indigo-900/30 rounded-2xl overflow-hidden shadow-lg animate-in fade-in slide-in-from-top-2">
            <button onClick={() => setOpen(v => !v)}
                className="w-full flex items-center gap-3 px-4 py-3 bg-indigo-950/20 text-left hover:bg-indigo-950/40 transition-colors">
                <div className="p-1.5 bg-indigo-500/10 rounded-lg">
                    <svg className={`w-3.5 h-3.5 transition-transform text-indigo-400 ${open ? "rotate-90" : ""}`}
                        viewBox="0 0 12 12" fill="currentColor"><path d="M4 2l5 4-5 4V2z" /></svg>
                </div>
                <div className="flex-1">
                    <span className="text-xs font-bold text-indigo-300 uppercase tracking-widest">Agent 推理全链路追踪</span>
                    <div className="text-[10px] text-indigo-400/60 mt-0.5">Chain-of-Thought 执行过程</div>
                </div>
                <span className="text-[10px] bg-indigo-500/20 text-indigo-400 px-2 py-0.5 rounded-full font-mono">
                    {steps.length} STEPS
                </span>
            </button>
            {open && (
                <div className="px-5 py-4 space-y-4 bg-gray-900/20 backdrop-blur-sm">
                    {steps.map((step, idx) => (
                        <div key={idx} className="flex gap-4 relative">
                            {/* 连接线 */}
                            {idx < steps.length - 1 && (
                                <div className="absolute left-[11px] top-6 bottom-[-16px] w-px bg-indigo-900/50" />
                            )}
                            
                            <div className={`w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold shrink-0 z-10
                                            ${step.hop === 0 
                                                ? "bg-amber-500/20 border border-amber-500/50 text-amber-500" 
                                                : "bg-indigo-600 border border-indigo-400 text-white shadow-[0_0_10px_rgba(79,70,229,0.4)]"}`}>
                                {step.hop === 0 ? "?" : step.hop}
                            </div>
                            <div className="flex-1 pb-2">
                                <div className="text-xs text-gray-200 font-medium leading-relaxed">{step.query}</div>
                                
                                {step.sub_queries && (
                                    <div className="mt-2 space-y-1.5">
                                        {step.sub_queries.map((sq, i) => (
                                            <div key={i} className="flex items-center gap-2 text-[11px] text-gray-500">
                                                <div className="w-1 h-1 rounded-full bg-gray-700" />
                                                {sq}
                                            </div>
                                        ))}
                                    </div>
                                )}

                                {(step.found !== undefined) && (
                                    <div className="text-[10px] text-gray-500 mt-1.5 flex items-center gap-2">
                                        <span className="flex items-center gap-1">
                                            <div className="w-1 h-1 rounded-full bg-emerald-500" />
                                            召回 {step.found} 个相关章节
                                        </span>
                                    </div>
                                )}
                                
                                {step.titles && step.titles.length > 0 && (
                                    <div className="flex flex-wrap gap-1.5 mt-2">
                                        {step.titles.map((t, i) => (
                                            <span key={i} className="text-[10px] bg-indigo-500/5 border border-indigo-500/10 text-indigo-400/70 px-2 py-0.5 rounded-md">
                                                {t}
                                            </span>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}
