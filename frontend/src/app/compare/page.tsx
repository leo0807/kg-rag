"use client";

import { useState, useEffect } from "react";
import { fetchApi } from "@/lib/api";
import { renderWordDiff } from "./diff";

interface Document {
    doc_id: string;
    title: string;
    version: string;
    sections: number;
}

interface Section {
    chunk_id: string;
    number: string;
    title: string;
    content: string;
}

interface DocDetail {
    doc_id: string;
    title: string;
    version: string;
    sections: Section[];
}

export default function ComparePage() {
    const [docs, setDocs]             = useState<Document[]>([]);
    const [leftId, setLeftId]         = useState("");
    const [rightId, setRightId]       = useState("");
    const [left, setLeft]             = useState<DocDetail | null>(null);
    const [right, setRight]           = useState<DocDetail | null>(null);
    const [loading, setLoading]       = useState(false);
    const [search, setSearch]         = useState("");
    const [showWordDiff, setShowWordDiff] = useState(true);

    useEffect(() => {
        fetchApi<{ data: Document[] }>("/api/documents?per_page=100")
            .then(d => setDocs(d.data));
    }, []);

    async function loadDoc(id: string, side: "left" | "right") {
        if (!id) return;
        setLoading(true);
        try {
            const data = await fetchApi<DocDetail>(`/api/documents/${id}`);
            if (side === "left") setLeft(data);
            else setRight(data);
        } finally {
            setLoading(false);
        }
    }

    function highlight(text: string) {
        if (!text) return "";
        if (!search.trim()) return text;
        const regex = new RegExp(
            `(${search.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "gi"
        );
        return text.replace(
            regex,
            '<mark class="bg-indigo-500/30 text-indigo-300 rounded px-0.5">$1</mark>'
        );
    }

    const leftSections  = left?.sections  ?? [];
    const rightSections = right?.sections ?? [];

    return (
        <div className="flex flex-col h-full bg-gray-950">

            {/* 顶部选择栏 */}
            <div className="flex flex-wrap items-end gap-4 px-6 py-4 border-b border-gray-800">
                <div className="flex-1 min-w-[160px]">
                    <label className="text-xs text-gray-500 mb-1 block">左侧文档</label>
                    <select
                        value={leftId}
                        onChange={e => { setLeftId(e.target.value); loadDoc(e.target.value, "left"); }}
                        className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg
                                   text-sm text-gray-200 outline-none focus:border-indigo-500"
                    >
                        <option value="">选择文档...</option>
                        {docs.map(d => (
                            <option key={d.doc_id} value={d.doc_id}>
                                {d.doc_id} {d.title ? `· ${d.title}` : ""}
                            </option>
                        ))}
                    </select>
                </div>

                <div className="flex-1 min-w-[160px]">
                    <label className="text-xs text-gray-500 mb-1 block">右侧文档</label>
                    <select
                        value={rightId}
                        onChange={e => { setRightId(e.target.value); loadDoc(e.target.value, "right"); }}
                        className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg
                                   text-sm text-gray-200 outline-none focus:border-indigo-500"
                    >
                        <option value="">选择文档...</option>
                        {docs.map(d => (
                            <option key={d.doc_id} value={d.doc_id}>
                                {d.doc_id} {d.title ? `· ${d.title}` : ""}
                            </option>
                        ))}
                    </select>
                </div>

                <div className="flex-1 min-w-[140px]">
                    <label className="text-xs text-gray-500 mb-1 block">高亮关键词</label>
                    <input
                        value={search}
                        onChange={e => setSearch(e.target.value)}
                        placeholder="输入关键词高亮..."
                        className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg
                                   text-sm text-gray-200 outline-none focus:border-indigo-500 placeholder-gray-600"
                    />
                </div>

                <button
                    onClick={() => setShowWordDiff(v => !v)}
                    className={`px-3 py-2 rounded-lg text-sm border transition-colors whitespace-nowrap ${
                        showWordDiff
                            ? "bg-indigo-600 border-indigo-500 text-white"
                            : "bg-gray-900 border-gray-700 text-gray-400 hover:text-white"
                    }`}
                >
                    {showWordDiff ? "词级差异 ON" : "词级差异 OFF"}
                </button>
            </div>

            {/* 对比区域 */}
            {loading && (
                <div className="flex items-center justify-center flex-1 text-gray-500 text-sm">加载中...</div>
            )}

            {!loading && (left || right) && (
                <div className="flex flex-1 overflow-hidden">
                    {/* 左侧 */}
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
                                        const isDiff   = rightSec !== undefined && rightSec.content !== sec.content;
                                        const aHtml    = isDiff && showWordDiff
                                            ? renderWordDiff(sec.content, rightSec!.content).aHtml
                                            : null;
                                        return (
                                            <div key={sec.chunk_id}
                                                className={`px-4 py-3 ${isDiff ? "bg-yellow-500/5 border-l-2 border-yellow-500/40" : ""}`}>
                                                <div className="text-xs font-mono text-indigo-400 mb-1">
                                                    §{sec.number} {sec.title}
                                                    {isDiff && <span className="ml-2 text-yellow-500/70">≠ 有差异</span>}
                                                </div>
                                                <div
                                                    className="text-xs text-gray-400 leading-relaxed whitespace-pre-wrap"
                                                    dangerouslySetInnerHTML={{
                                                        __html: aHtml !== null
                                                            ? highlight(aHtml)
                                                            : highlight(sec.content)
                                                    }}
                                                />
                                            </div>
                                        );
                                    })}
                                </div>
                            </>
                        )}
                    </div>

                    {/* 右侧 */}
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
                                        const isDiff  = leftSec !== undefined && leftSec.content !== sec.content;
                                        const bHtml   = isDiff && showWordDiff
                                            ? renderWordDiff(leftSec!.content, sec.content).bHtml
                                            : null;
                                        return (
                                            <div key={sec.chunk_id}
                                                className={`px-4 py-3 ${isDiff ? "bg-yellow-500/5 border-l-2 border-yellow-500/40" : ""}`}>
                                                <div className="text-xs font-mono text-indigo-400 mb-1">
                                                    §{sec.number} {sec.title}
                                                    {isDiff && <span className="ml-2 text-yellow-500/70">≠ 有差异</span>}
                                                </div>
                                                <div
                                                    className="text-xs text-gray-400 leading-relaxed whitespace-pre-wrap"
                                                    dangerouslySetInnerHTML={{
                                                        __html: bHtml !== null
                                                            ? highlight(bHtml)
                                                            : highlight(sec.content)
                                                    }}
                                                />
                                            </div>
                                        );
                                    })}
                                </div>
                            </>
                        )}
                    </div>
                </div>
            )}

            {!loading && !left && !right && (
                <div className="flex items-center justify-center flex-1 text-gray-600 text-sm">
                    请选择两个文档进行对比
                </div>
            )}
        </div>
    );
}
