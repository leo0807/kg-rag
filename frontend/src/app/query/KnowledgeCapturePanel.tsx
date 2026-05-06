"use client";

import { BrainCircuit, Check, ChevronDown, ChevronUp } from "lucide-react";
import { useEffect, useState } from "react";
import { fetchApi } from "@/lib/api";

interface Triple { subject: string; predicate: string; object: string; }

interface Props {
    answerText: string;
}

export function KnowledgeCapturePanel({ answerText }: Props) {
    const [open, setOpen]         = useState(false);
    const [loading, setLoading]   = useState(false);
    const [saving, setSaving]     = useState(false);
    const [triples, setTriples]   = useState<Triple[]>([]);
    const [selected, setSelected] = useState<Set<number>>(new Set());
    const [done, setDone]         = useState(false);

    useEffect(() => { setTriples([]); setSelected(new Set()); setDone(false); }, [answerText]);

    async function extract() {
        if (!answerText.trim()) return;
        setLoading(true);
        try {
            const res = await fetchApi<{ triples: Triple[] }>("/api/knowledge/extract", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ text: answerText }),
            });
            setTriples(res.triples);
            setSelected(new Set(res.triples.map((_, i) => i)));
        } finally { setLoading(false); }
    }

    async function capture() {
        const chosen = triples.filter((_, i) => selected.has(i));
        if (!chosen.length) return;
        setSaving(true);
        try {
            await fetchApi("/api/knowledge/capture", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ triples: chosen }),
            });
            setDone(true);
        } finally { setSaving(false); }
    }

    function toggleAll() {
        setSelected(selected.size === triples.length ? new Set() : new Set(triples.map((_, i) => i)));
    }

    function toggle(i: number) {
        const next = new Set(selected);
        if (next.has(i)) next.delete(i); else next.add(i);
        setSelected(next);
    }

    return (
        <div className="mt-2 border border-gray-700/60 rounded-lg overflow-hidden">
            <button type="button" onClick={() => { setOpen(v => !v); if (!open && triples.length === 0) extract(); }}
                className="w-full flex items-center gap-2 px-3 py-2 bg-gray-800/60 hover:bg-gray-800 text-xs text-gray-400 transition-colors">
                <BrainCircuit size={12} className="text-violet-400 shrink-0" />
                <span className="flex-1 text-left">从回答中捕获知识三元组</span>
                {open ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            </button>

            {open && (
                <div className="bg-gray-900/80 px-3 py-2">
                    {loading && <div className="text-xs text-gray-500 py-2">AI 分析中...</div>}
                    {done && <div className="flex items-center gap-1.5 text-xs text-green-400 py-2"><Check size={12} />已写入知识图谱</div>}
                    {!loading && !done && triples.length === 0 && (
                        <button type="button" onClick={extract} className="text-xs text-indigo-400 hover:text-indigo-300 py-1">重新分析</button>
                    )}
                    {!loading && !done && triples.length > 0 && (
                        <>
                            <div className="flex items-center justify-between mb-2">
                                <span className="text-[11px] text-gray-500">发现 {triples.length} 个三元组</span>
                                <button type="button" onClick={toggleAll} className="text-[11px] text-indigo-400 hover:text-indigo-300">
                                    {selected.size === triples.length ? "取消全选" : "全选"}
                                </button>
                            </div>
                            <div className="space-y-1.5 max-h-40 overflow-y-auto">
                                {triples.map((t, i) => (
                                    <label key={`${t.subject}-${t.predicate}-${t.object}-${i}`} className="flex items-start gap-2 cursor-pointer">
                                        <input type="checkbox" checked={selected.has(i)} onChange={() => toggle(i)}
                                            className="mt-0.5 accent-indigo-500 shrink-0" />
                                        <span className="text-[11px] text-gray-300 leading-relaxed">
                                            <span className="text-indigo-300">{t.subject}</span>
                                            <span className="text-gray-500 mx-1">—{t.predicate}→</span>
                                            <span className="text-emerald-300">{t.object}</span>
                                        </span>
                                    </label>
                                ))}
                            </div>
                            <button type="button" onClick={capture} disabled={saving || selected.size === 0}
                                className="mt-2 px-3 py-1.5 w-full rounded bg-violet-600/30 border border-violet-500/40 text-violet-300 text-xs hover:bg-violet-600/50 disabled:opacity-40">
                                {saving ? "写入中..." : `写入图谱 (${selected.size})`}
                            </button>
                        </>
                    )}
                </div>
            )}
        </div>
    );
}
