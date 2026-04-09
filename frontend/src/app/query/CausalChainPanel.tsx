"use client";

import { useState } from "react";
import { CausalChainData } from "./types";

export function CausalChainPanel({ data }: { data: CausalChainData }) {
    const [open, setOpen] = useState(true);
    const intent = data.intent;
    const typeLabel: Record<string, string> = {
        Process: "工序", Tool: "工具", Material: "材料", Constraint: "约束",
    };

    return (
        <div className="mb-4 border border-amber-800/40 rounded-xl overflow-hidden bg-amber-950/10">
            <button
                onClick={() => setOpen(v => !v)}
                className="w-full flex items-center gap-2 px-4 py-2.5 text-left hover:bg-amber-900/10 transition-colors"
            >
                <svg className={`w-3 h-3 transition-transform text-amber-500 ${open ? "rotate-90" : ""}`}
                    viewBox="0 0 12 12" fill="currentColor"><path d="M4 2l5 4-5 4V2z" /></svg>
                <span className="text-xs text-amber-400 font-medium">反事实因果链分析</span>
                {intent.removed_name && (
                    <span className="ml-1 px-1.5 py-0.5 bg-amber-800/30 text-amber-300 text-xs rounded">
                        去掉：{intent.removed_name}
                    </span>
                )}
                <span className="ml-auto text-xs text-amber-700">
                    {data.affected_sections.length} 个受影响章节
                </span>
            </button>

            {open && (
                <div className="px-4 pb-4 space-y-3">
                    {/* 意图摘要 */}
                    <div className="flex flex-wrap gap-2 pt-1 text-xs">
                        {intent.removed_name && (
                            <span className="px-2 py-1 bg-red-900/30 border border-red-800/40 text-red-400 rounded-lg">
                                ❌ 移除 {typeLabel[intent.removed_type] || ""} · {intent.removed_name}
                            </span>
                        )}
                        {intent.subject && (
                            <span className="px-2 py-1 bg-gray-800 text-gray-400 rounded-lg">
                                主体：{intent.subject}
                            </span>
                        )}
                        {intent.requirement && (
                            <span className="px-2 py-1 bg-gray-800 text-gray-400 rounded-lg">
                                目标：{intent.requirement}
                            </span>
                        )}
                    </div>

                    {/* 受影响章节 + 约束 */}
                    {data.affected_sections.length > 0 && (
                        <div>
                            <div className="text-xs text-gray-500 mb-1.5">受影响章节与约束</div>
                            <div className="space-y-1.5">
                                {data.affected_sections.slice(0, 5).map(sec => (
                                    <div key={sec.chunk_id}
                                        className="flex items-start gap-2 bg-gray-900/60 rounded-lg px-3 py-2">
                                        <span className="text-xs text-amber-600 shrink-0 mt-0.5">⚠</span>
                                        <div className="min-w-0">
                                            <span className="text-xs text-indigo-400 font-mono mr-1">
                                                {sec.doc_id} §{sec.number}
                                            </span>
                                            <span className="text-xs text-gray-300">{sec.title}</span>
                                            {sec.constraints.length > 0 && (
                                                <div className="flex flex-wrap gap-1 mt-1">
                                                    {sec.constraints.slice(0, 3).map((c, i) => (
                                                        <span key={i}
                                                            className="text-xs bg-amber-900/20 border border-amber-800/30 text-amber-400 px-1.5 py-0.5 rounded">
                                                            {(c.description || c.type || "").trim()}
                                                            {c.value && ` ${c.value}${c.value_max ? "~" + c.value_max : ""} ${c.unit || ""}`.trim()}
                                                        </span>
                                                    ))}
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* 替代方案 */}
                    <div>
                        <div className="text-xs text-gray-500 mb-1.5">替代方案</div>
                        {data.alternatives.length > 0 ? (
                            <div className="flex flex-wrap gap-1.5">
                                {data.alternatives.map((alt, i) => (
                                    <span key={i}
                                        className="text-xs bg-emerald-900/20 border border-emerald-800/30 text-emerald-400 px-2 py-0.5 rounded-lg">
                                        ✓ {alt}
                                    </span>
                                ))}
                            </div>
                        ) : (
                            <span className="text-xs text-gray-600">图谱中未发现已知替代方案</span>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}
