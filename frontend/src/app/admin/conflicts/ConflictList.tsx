"use client";

import { ChevronDown, ChevronUp } from "lucide-react";
import type { ConflictItem, Severity, ConflictType, Status } from "./useConflicts";
import { SEVERITY_STYLE, STATUS_STYLE, STATUS_LABELS } from "./useConflicts";
import { ConflictDetail } from "./ConflictDetail";

function SeverityBadge({ s }: { s: Severity }) {
    return (
        <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${SEVERITY_STYLE[s]}`}>
            {s === "high" ? "高" : s === "medium" ? "中" : "低"}
        </span>
    );
}

function TypeBadge({ t }: { t: ConflictType }) {
    return (
        <span className={`inline-flex rounded-full px-2 py-0.5 text-xs ${
            t === "constraint" ? "bg-violet-500/15 text-violet-400" : "bg-cyan-500/15 text-cyan-400"
        }`}>
            {t === "constraint" ? "约束" : "语义"}
        </span>
    );
}

interface Props {
    conflicts: ConflictItem[];
    expanded: Set<number>;
    updating: number | null;
    onToggle: (id: number) => void;
    onChangeStatus: (id: number, status: Status) => void;
}

export function ConflictList({ conflicts, expanded, updating, onToggle, onChangeStatus }: Props) {
    if (conflicts.length === 0) {
        return (
            <div className="text-center py-16 text-gray-500">
                暂无冲突记录。点击「开始扫描」触发检测。
            </div>
        );
    }

    return (
        <div className="space-y-3">
            {conflicts.map(c => {
                const isExpanded = expanded.has(c.id);
                return (
                    <div
                        key={c.id}
                        className={`rounded-2xl border transition-colors ${
                            c.status === "dismissed" ? "border-gray-800/60 opacity-60"
                            : c.severity === "high" ? "border-rose-800/40 bg-rose-950/10"
                            : "border-gray-800 bg-gray-900"
                        }`}
                    >
                        <div className="flex items-start gap-3 p-4 cursor-pointer" onClick={() => onToggle(c.id)}>
                            <div className="flex-1 min-w-0 space-y-1">
                                <div className="flex items-center gap-2 flex-wrap">
                                    <SeverityBadge s={c.severity} />
                                    <TypeBadge t={c.conflict_type} />
                                    <span className="text-gray-300 font-medium truncate">{c.entity_name}</span>
                                    <span className="text-gray-500 text-xs">{c.entity_type}</span>
                                </div>
                                <div className="text-sm text-gray-400 line-clamp-2">{c.description}</div>
                                <div className="text-xs text-gray-600">{c.section_a_doc_id} ↔ {c.section_b_doc_id}</div>
                            </div>
                            <div className="flex items-center gap-2 shrink-0">
                                <span className={`text-xs px-2 py-0.5 rounded-full ${STATUS_STYLE[c.status]}`}>
                                    {STATUS_LABELS[c.status]}
                                </span>
                                {isExpanded ? <ChevronUp size={15} className="text-gray-500" /> : <ChevronDown size={15} className="text-gray-500" />}
                            </div>
                        </div>

                        {isExpanded && (
                            <ConflictDetail c={c} updating={updating} onChangeStatus={onChangeStatus} />
                        )}
                    </div>
                );
            })}
        </div>
    );
}
