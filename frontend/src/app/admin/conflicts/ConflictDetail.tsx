"use client";

import { CheckCircle2, ChevronDown, Loader2, XCircle } from "lucide-react";
import type { ConflictItem, Status } from "./useConflicts";
import { STATUS_LABELS } from "./useConflicts";

interface Props {
    c: ConflictItem;
    updating: number | null;
    onChangeStatus: (id: number, status: Status) => void;
}

export function ConflictDetail({ c, updating, onChangeStatus }: Props) {
    return (
        <div className="border-t border-gray-800 p-4 space-y-4">
            <div className="grid md:grid-cols-2 gap-4">
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

            <div className="flex items-center gap-2">
                <span className="text-xs text-gray-500 mr-1">标记为：</span>
                {(["confirmed", "dismissed", "resolved"] as Status[]).map(s => (
                    <button
                        key={s}
                        type="button"
                        disabled={c.status === s || updating === c.id}
                        onClick={() => onChangeStatus(c.id, s)}
                        className={`inline-flex items-center gap-1 px-3 h-7 rounded-lg text-xs transition-colors disabled:opacity-40 ${
                            s === "confirmed" ? "bg-rose-700/40 text-rose-300 hover:bg-rose-700/60"
                            : s === "dismissed" ? "bg-gray-800 text-gray-400 hover:bg-gray-700"
                            : "bg-emerald-700/40 text-emerald-300 hover:bg-emerald-700/60"
                        }`}
                    >
                        {s === "confirmed" && <XCircle size={11} />}
                        {s === "dismissed" && <ChevronDown size={11} />}
                        {s === "resolved" && <CheckCircle2 size={11} />}
                        {STATUS_LABELS[s]}
                        {updating === c.id && <Loader2 size={11} className="animate-spin" />}
                    </button>
                ))}
            </div>
        </div>
    );
}
