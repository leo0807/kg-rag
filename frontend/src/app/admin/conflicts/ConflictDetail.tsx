"use client";

import { Loader2 } from "lucide-react";
import { useState } from "react";
import type { ConflictItem, Status } from "./useConflicts";

const DECISIONS = [
    { value: "use_a",           label: "以文档 A 为准（较新或权威版本）" },
    { value: "use_b",           label: "以文档 B 为准（更高要求）" },
    { value: "both_applicable", label: "两者均适用（适用场景不同）" },
    { value: "expert_review",   label: "标记为待确认（需专家介入）" },
] as const;

type Decision = (typeof DECISIONS)[number]["value"];

interface Props {
    c: ConflictItem;
    updating: number | null;
    onChangeStatus: (id: number, status: Status) => void;
    onArbitrate: (id: number, decision: string, note: string) => void;
}

export function ConflictDetail({ c, updating, onArbitrate }: Props) {
    const [decision, setDecision] = useState<Decision | "">("");
    const [note, setNote] = useState("");
    const busy = updating === c.id;

    function handleSubmit() {
        if (!decision) return;
        onArbitrate(c.id, decision, note);
    }

    function handleDefer() {
        onArbitrate(c.id, "expert_review", note);
    }

    return (
        <div className="border-t border-gray-800 p-4 space-y-4">
            {/* Section comparison */}
            <div className="grid md:grid-cols-2 gap-3">
                <div className="rounded-xl bg-gray-950 border border-gray-800 p-3 text-sm space-y-1">
                    <div className="text-xs text-gray-500 mb-2">文档 A · {c.section_a_doc_id}</div>
                    <div className="text-gray-300 font-medium">{c.section_a_title}</div>
                    <div className="text-gray-400 text-xs whitespace-pre-wrap line-clamp-6">{c.section_a_snippet}</div>
                </div>
                <div className="rounded-xl bg-gray-950 border border-gray-800 p-3 text-sm space-y-1">
                    <div className="text-xs text-gray-500 mb-2">文档 B · {c.section_b_doc_id}</div>
                    <div className="text-gray-300 font-medium">{c.section_b_title}</div>
                    <div className="text-gray-400 text-xs whitespace-pre-wrap line-clamp-6">{c.section_b_snippet}</div>
                </div>
            </div>

            {/* Arbitration form */}
            <div className="rounded-xl bg-gray-900/60 border border-gray-700 p-4 space-y-3">
                <div className="text-xs font-semibold text-gray-400 uppercase tracking-wide">仲裁决定</div>
                <div className="space-y-2">
                    {DECISIONS.map(d => (
                        <label key={d.value} className="flex items-center gap-2.5 cursor-pointer group">
                            <input
                                type="radio"
                                name={`arb_${c.id}`}
                                value={d.value}
                                checked={decision === d.value}
                                onChange={() => setDecision(d.value)}
                                disabled={busy}
                                className="accent-indigo-500"
                            />
                            <span className="text-sm text-gray-300 group-hover:text-gray-100 transition-colors">
                                {d.label}
                            </span>
                        </label>
                    ))}
                </div>

                <div>
                    <textarea
                        rows={2}
                        value={note}
                        onChange={e => setNote(e.target.value)}
                        disabled={busy}
                        placeholder="仲裁说明（可选）…"
                        className="w-full rounded-lg bg-gray-950 border border-gray-700 px-3 py-2 text-sm text-gray-300 placeholder-gray-600 resize-none focus:outline-none focus:border-indigo-500 disabled:opacity-50"
                    />
                </div>

                <div className="flex gap-2">
                    <button
                        type="button"
                        disabled={!decision || busy}
                        onClick={handleSubmit}
                        className="inline-flex items-center gap-1.5 px-4 h-8 rounded-lg text-sm bg-indigo-600 text-white hover:bg-indigo-500 disabled:opacity-40 transition-colors"
                    >
                        {busy && <Loader2 size={13} className="animate-spin" />}
                        提交仲裁
                    </button>
                    <button
                        type="button"
                        disabled={busy}
                        onClick={handleDefer}
                        className="inline-flex items-center gap-1.5 px-4 h-8 rounded-lg text-sm bg-gray-800 text-gray-300 hover:bg-gray-700 disabled:opacity-40 transition-colors"
                    >
                        暂缓处理
                    </button>
                </div>
            </div>
        </div>
    );
}
