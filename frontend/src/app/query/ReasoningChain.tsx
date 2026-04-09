"use client";

import { useState } from "react";

export interface ReasoningStep {
    hop: number;
    query: string;
    found: number;
    titles: string[];
}

export function ReasoningChain({ steps }: { steps: ReasoningStep[] }) {
    const [open, setOpen] = useState(false);
    if (!steps.length) return null;
    return (
        <div className="mb-4 border border-gray-800 rounded-xl overflow-hidden">
            <button onClick={() => setOpen(v => !v)}
                className="w-full flex items-center gap-2 px-4 py-2.5 bg-gray-900 text-left hover:bg-gray-800/50 transition-colors">
                <svg className={`w-3 h-3 transition-transform text-gray-500 ${open ? "rotate-90" : ""}`}
                    viewBox="0 0 12 12" fill="currentColor"><path d="M4 2l5 4-5 4V2z" /></svg>
                <span className="text-xs text-gray-500">多跳推理过程</span>
                <span className="ml-auto text-xs text-gray-600">{steps.length} 跳</span>
            </button>
            {open && (
                <div className="px-4 py-3 space-y-3 bg-gray-950">
                    {steps.map(step => (
                        <div key={step.hop} className="flex gap-3">
                            <div className="w-5 h-5 rounded-full bg-indigo-900 border border-indigo-700
                                            flex items-center justify-center text-xs text-indigo-400 shrink-0">
                                {step.hop}
                            </div>
                            <div>
                                <div className="text-xs text-gray-300 font-medium">{step.query}</div>
                                <div className="text-xs text-gray-600 mt-0.5">找到 {step.found} 个章节</div>
                                {step.titles.length > 0 && (
                                    <div className="flex flex-wrap gap-1 mt-1">
                                        {step.titles.map((t, i) => (
                                            <span key={i} className="text-xs bg-gray-800 text-gray-400 px-1.5 py-0.5 rounded">
                                                {t.length > 30 ? t.slice(0, 30) + "…" : t}
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
