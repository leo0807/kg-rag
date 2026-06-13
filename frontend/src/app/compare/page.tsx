"use client";

import { useState, useEffect, useMemo } from "react";
import { fetchApi, getApiBaseUrl, getAuthHeaders } from "@/lib/api";
import { renderWordDiff } from "./diff";
import { Search, FileDown } from "lucide-react";
import { DocSelector, type Document } from "./DocSelector";
import { GraphDiffPanel, type GraphChanges } from "./GraphDiffPanel";

interface Section { chunk_id: string; number: string; title: string; content: string; }
interface DocDetail { doc_id: string; title: string; version: string; sections: Section[]; }

export default function ComparePage() {
    const [docs, setDocs]     = useState<Document[]>([]);
    const [leftId, setLeftId] = useState("");
    const [rightId, setRightId] = useState("");
    const [left, setLeft]     = useState<DocDetail | null>(null);
    const [right, setRight]   = useState<DocDetail | null>(null);
    const [loading, setLoading]       = useState(false);
    const [exporting, setExporting]   = useState(false);
    const [search, setSearch]         = useState("");
    const [showWordDiff, setShowWordDiff] = useState(true);
    const [graphChanges, setGraphChanges] = useState<GraphChanges | null>(null);

    useEffect(() => {
        fetchApi<{ data: Document[] }>("/api/documents?per_page=1000").then(d => setDocs(d.data));
    }, []);

    useEffect(() => {
        if (!leftId || !rightId) { setGraphChanges(null); return; }
        fetchApi<{ graph_changes: GraphChanges }>("/api/compare/documents", {
            method: "POST", body: JSON.stringify({ doc_id_a: leftId, doc_id_b: rightId }),
        }).then(d => setGraphChanges(d.graph_changes)).catch(() => setGraphChanges(null));
    }, [leftId, rightId]);

    async function loadDoc(id: string, side: "left" | "right") {
        if (!id) return;
        setLoading(true);
        try {
            const data = await fetchApi<DocDetail>(`/api/documents/${id}`);
            if (side === "left") setLeft(data); else setRight(data);
        } finally { setLoading(false); }
    }

    const diffSummary = useMemo(() => {
        if (!left || !right) return null;
        const mapA = new Map(left.sections.map(s => [s.number, s]));
        const mapB = new Map(right.sections.map(s => [s.number, s]));
        const added   = right.sections.filter(s => !mapA.has(s.number)).map(s => s.number);
        const removed = left.sections.filter(s => !mapB.has(s.number)).map(s => s.number);
        const modified = left.sections
            .filter(s => mapB.has(s.number) && mapB.get(s.number)!.content !== s.content)
            .map(s => s.number);
        return { added: new Set(added), removed: new Set(removed), modified: new Set(modified) };
    }, [left, right]);

    function highlight(text: string) {
        if (!text || !search.trim()) return text;
        const re = new RegExp(`(${search.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "gi");
        return text.replace(re, '<mark class="bg-indigo-500/30 text-indigo-300 rounded px-0.5">$1</mark>');
    }

    async function exportDocx() {
        if (!leftId || !rightId) return;
        setExporting(true);
        try {
            const headers = await getAuthHeaders({ "Content-Type": "application/json" });
            const res = await fetch(`${getApiBaseUrl()}/api/compare/export-docx`, {
                method: "POST", headers,
                body: JSON.stringify({ doc_id_a: leftId, doc_id_b: rightId }),
            });
            const blob = await res.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url; a.download = `compare_${leftId}_vs_${rightId}.docx`; a.click();
            URL.revokeObjectURL(url);
        } finally { setExporting(false); }
    }

    function sectionBorder(number: string, side: "left" | "right") {
        if (!diffSummary) return "";
        if (diffSummary.modified.has(number)) return "bg-yellow-500/5 border-l-2 border-yellow-500/40";
        if (side === "left" && diffSummary.removed.has(number)) return "bg-red-500/5 border-l-2 border-red-500/40";
        if (side === "right" && diffSummary.added.has(number)) return "bg-green-500/5 border-l-2 border-green-500/40";
        return "";
    }

    const leftSections  = left?.sections  ?? [];
    const rightSections = right?.sections ?? [];

    return (
        <div className="flex flex-col h-full bg-gray-950">
            <div className="flex flex-wrap items-end gap-4 px-6 py-4 border-b border-gray-800">
                <DocSelector docs={docs} selectedId={leftId} onSelect={(id) => { setLeftId(id); loadDoc(id, "left"); }} label="左侧文档" />
                <DocSelector docs={docs} selectedId={rightId} onSelect={(id) => { setRightId(id); loadDoc(id, "right"); }} label="右侧文档" />
                <div className="flex-1 min-w-[140px]">
                    <label className="text-xs text-gray-500 mb-1 block">高亮关键词</label>
                    <div className="relative">
                        <Search size={14} className="absolute left-2.5 top-2.5 text-gray-500" />
                        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="输入关键词..."
                            className="w-full pl-8 pr-3 py-2 bg-gray-900 border border-gray-700 rounded-lg text-sm text-gray-200 outline-none focus:border-indigo-500 placeholder-gray-600" />
                    </div>
                </div>
                <button onClick={() => setShowWordDiff(v => !v)}
                    className={`px-3 py-2 rounded-lg text-sm border transition-colors whitespace-nowrap ${showWordDiff ? "bg-indigo-600 border-indigo-500 text-white" : "bg-gray-900 border-gray-700 text-gray-400 hover:text-white"}`}>
                    {showWordDiff ? "词级差异 ON" : "词级差异 OFF"}
                </button>
                {left && right && (
                    <button onClick={exportDocx} disabled={exporting}
                        className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm bg-gray-800 border border-gray-700 text-gray-300 hover:text-white disabled:opacity-40 whitespace-nowrap">
                        <FileDown size={14} />{exporting ? "导出中..." : "导出对比报告"}
                    </button>
                )}
            </div>

            {/* Diff summary badges */}
            {diffSummary && (diffSummary.added.size + diffSummary.removed.size + diffSummary.modified.size > 0) && (
                <div className="flex items-center gap-3 px-6 py-2 border-b border-gray-800 bg-gray-900/50">
                    <span className="text-xs text-gray-500">差异摘要：</span>
                    {diffSummary.added.size > 0   && <span className="px-2 py-0.5 rounded-full text-xs bg-green-500/15 text-green-400 border border-green-500/30">+{diffSummary.added.size} 新增</span>}
                    {diffSummary.modified.size > 0 && <span className="px-2 py-0.5 rounded-full text-xs bg-yellow-500/15 text-yellow-400 border border-yellow-500/30">~{diffSummary.modified.size} 修改</span>}
                    {diffSummary.removed.size > 0  && <span className="px-2 py-0.5 rounded-full text-xs bg-red-500/15 text-red-400 border border-red-500/30">-{diffSummary.removed.size} 删除</span>}
                </div>
            )}

            {loading && <div className="flex items-center justify-center flex-1 text-gray-500 text-sm">加载中...</div>}

            {!loading && (left || right) && (
                <div className="flex flex-col flex-1 overflow-hidden">
                <div className="flex flex-1 overflow-hidden">
                    <div className="flex-1 overflow-auto border-r border-gray-800">
                        {left && (
                            <>
                                <div className="sticky top-0 px-4 py-3 bg-gray-900 border-b border-gray-800 z-10">
                                    <div className="text-sm font-medium text-white">{left.doc_id}</div>
                                    <div className="text-xs text-gray-500">{left.title} · v{left.version}</div>
                                </div>
                                <div className="divide-y divide-gray-800/50">
                                    {leftSections.map(sec => {
                                        const rightSec = right?.sections.find(s => s.number === sec.number);
                                        const isDiff = rightSec !== undefined && rightSec.content !== sec.content;
                                        const aHtml = isDiff && showWordDiff ? renderWordDiff(sec.content, rightSec!.content).aHtml : null;
                                        return (
                                            <div key={sec.chunk_id} className={`px-4 py-3 ${sectionBorder(sec.number, "left")}`}>
                                                <div className="text-xs font-mono text-indigo-400 mb-1">
                                                    §{sec.number} {sec.title}
                                                    {isDiff && <span className="ml-2 text-yellow-500/70">≠ 有差异</span>}
                                                    {diffSummary?.removed.has(sec.number) && <span className="ml-2 text-red-400/70">已删除</span>}
                                                </div>
                                                <div className="text-xs text-gray-400 leading-relaxed whitespace-pre-wrap"
                                                    dangerouslySetInnerHTML={{ __html: aHtml !== null ? highlight(aHtml) : highlight(sec.content) }} />
                                            </div>
                                        );
                                    })}
                                </div>
                            </>
                        )}
                    </div>
                    <div className="flex-1 overflow-auto">
                        {right && (
                            <>
                                <div className="sticky top-0 px-4 py-3 bg-gray-900 border-b border-gray-800 z-10">
                                    <div className="text-sm font-medium text-white">{right.doc_id}</div>
                                    <div className="text-xs text-gray-500">{right.title} · v{right.version}</div>
                                </div>
                                <div className="divide-y divide-gray-800/50">
                                    {rightSections.map(sec => {
                                        const leftSec = left?.sections.find(s => s.number === sec.number);
                                        const isDiff = leftSec !== undefined && leftSec.content !== sec.content;
                                        const bHtml = isDiff && showWordDiff ? renderWordDiff(leftSec!.content, sec.content).bHtml : null;
                                        return (
                                            <div key={sec.chunk_id} className={`px-4 py-3 ${sectionBorder(sec.number, "right")}`}>
                                                <div className="text-xs font-mono text-indigo-400 mb-1">
                                                    §{sec.number} {sec.title}
                                                    {isDiff && <span className="ml-2 text-yellow-500/70">≠ 有差异</span>}
                                                    {diffSummary?.added.has(sec.number) && <span className="ml-2 text-green-400/70">新增</span>}
                                                </div>
                                                <div className="text-xs text-gray-400 leading-relaxed whitespace-pre-wrap"
                                                    dangerouslySetInnerHTML={{ __html: bHtml !== null ? highlight(bHtml) : highlight(sec.content) }} />
                                            </div>
                                        );
                                    })}
                                </div>
                            </>
                        )}
                    </div>
                </div>
                {graphChanges && <GraphDiffPanel changes={graphChanges} />}
                </div>
            )}

            {!loading && !left && !right && (
                <div className="flex items-center justify-center flex-1 text-gray-600 text-sm">请选择两个文档进行对比</div>
            )}
        </div>
    );
}
