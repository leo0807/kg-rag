"use client";
import { useState } from "react";
import { fetchApi } from "@/lib/api";

export interface PendingSection {
    chunk_id: string; title: string; content: string; confidence: number; doc_id: string;
}

interface Props {
    sections: PendingSection[];
    onProgress: (done: number) => void;
}

function ConfidenceBadge({ value }: { value: number }) {
    const pct = Math.round(value * 100);
    const cls = pct >= 80 ? "text-green-400 bg-green-500/10" : pct >= 60 ? "text-yellow-400 bg-yellow-500/10" : "text-red-400 bg-red-500/10";
    return <span className={`px-2 py-0.5 rounded text-xs font-mono ${cls}`}>置信度 {pct}%</span>;
}

export function SectionReviewer({ sections, onProgress }: Props) {
    const [idx, setIdx]           = useState(0);
    const [title, setTitle]       = useState("");
    const [content, setContent]   = useState("");
    const [saving, setSaving]     = useState(false);
    const [doneCount, setDoneCount] = useState(0);

    const total = sections.length;
    const current = sections[idx];

    function initEdit(sec: PendingSection) {
        setTitle(sec.title); setContent(sec.content);
    }

    function advance(delta = 1) {
        const next = idx + delta;
        if (next >= 0 && next < total) { setIdx(next); initEdit(sections[next]); }
    }

    // Initialize on first render
    if (current && title === "" && content === "") { initEdit(current); }

    async function save() {
        if (!current) return;
        setSaving(true);
        try {
            await fetchApi(`/api/annotation/sections/${encodeURIComponent(current.chunk_id)}`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ title, content }),
            });
            const d = doneCount + 1; setDoneCount(d); onProgress(d);
            advance();
        } finally { setSaving(false); }
    }

    if (!current) return <div className="text-gray-500 text-sm py-8 text-center">✅ 所有章节已审核完成</div>;

    const progress = Math.round((doneCount / total) * 100);

    return (
        <div className="space-y-4">
            {/* Progress */}
            <div className="flex items-center gap-3">
                <div className="flex-1 h-1.5 bg-gray-800 rounded-full overflow-hidden">
                    <div className="h-full bg-indigo-500 transition-all" style={{ width: `${progress}%` }} />
                </div>
                <span className="text-xs text-gray-500 whitespace-nowrap">已完成 {doneCount} / {total}</span>
            </div>

            {/* Card */}
            <div className="border border-gray-700 rounded-xl overflow-hidden">
                <div className="flex items-center justify-between px-4 py-2.5 bg-gray-800/80 border-b border-gray-700">
                    <div className="flex items-center gap-2">
                        <span className="text-xs font-mono text-indigo-400">{current.doc_id}</span>
                        <span className="text-xs text-gray-300">{current.chunk_id}</span>
                    </div>
                    <ConfidenceBadge value={current.confidence} />
                </div>
                <div className="grid grid-cols-2 divide-x divide-gray-700">
                    <div className="p-4">
                        <div className="text-xs text-gray-500 mb-2">原始内容</div>
                        <p className="text-xs text-gray-400 leading-relaxed whitespace-pre-wrap font-mono break-all">{current.content}</p>
                    </div>
                    <div className="p-4 flex flex-col gap-3">
                        <div>
                            <div className="text-xs text-gray-500 mb-1.5">修正标题</div>
                            <input value={title} onChange={e => setTitle(e.target.value)}
                                className="w-full px-2.5 py-1.5 bg-gray-800 border border-gray-700 rounded text-xs text-gray-200 outline-none focus:border-indigo-500" />
                        </div>
                        <div className="flex-1">
                            <div className="text-xs text-gray-500 mb-1.5">修正内容</div>
                            <textarea value={content} onChange={e => setContent(e.target.value)} rows={8}
                                className="w-full px-2.5 py-1.5 bg-gray-800 border border-gray-700 rounded text-xs text-gray-200 outline-none focus:border-indigo-500 resize-none" />
                        </div>
                    </div>
                </div>
                <div className="flex items-center justify-between px-4 py-3 border-t border-gray-700 bg-gray-900/50">
                    <span className="text-xs text-gray-600">{idx + 1} / {total}</span>
                    <div className="flex gap-2">
                        <button onClick={() => advance()} className="px-3 py-1.5 rounded text-xs text-gray-500 hover:text-gray-300 hover:bg-gray-800">跳过</button>
                        <button onClick={save} disabled={saving}
                            className="px-4 py-1.5 rounded bg-indigo-600 text-white text-xs hover:bg-indigo-500 disabled:opacity-40">
                            {saving ? "保存中..." : "保存修正"}
                        </button>
                        <button onClick={() => advance()} className="px-3 py-1.5 rounded bg-gray-800 text-xs text-gray-300 hover:bg-gray-700">下一个 →</button>
                    </div>
                </div>
            </div>
        </div>
    );
}
