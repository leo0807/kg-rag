"use client";

import { useState, useEffect } from "react";
import { fetchApi } from "@/lib/api";

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

// ── Myers diff（词级别）────────────────────────────────────────────────────────
type DiffOp = { type: "equal" | "insert" | "delete"; text: string };

function myersDiff(a: string[], b: string[]): DiffOp[] {
    const n = a.length, m = b.length;
    const max = n + m;
    if (max === 0) return [];
    const v = new Array(2 * max + 1).fill(0);
    const trace: number[][] = [];

    for (let d = 0; d <= max; d++) {
        trace.push([...v]);
        for (let k = -d; k <= d; k += 2) {
            const idx = k + max;
            let x: number;
            if (k === -d || (k !== d && v[idx - 1] < v[idx + 1])) {
                x = v[idx + 1];
            } else {
                x = v[idx - 1] + 1;
            }
            let y = x - k;
            while (x < n && y < m && a[x] === b[y]) { x++; y++; }
            v[idx] = x;
            if (x >= n && y >= m) return _backtrack(trace, a, b, max);
        }
    }
    return _backtrack(trace, a, b, max);
}

function _backtrack(trace: number[][], a: string[], b: string[], max: number): DiffOp[] {
    const ops: DiffOp[] = [];
    let x = a.length, y = b.length;
    for (let d = trace.length - 1; d >= 0; d--) {
        const v = trace[d];
        const k = x - y;
        const idx = k + max;
        let prevK: number;
        if (k === -d || (k !== d && (v[idx - 1] ?? 0) < (v[idx + 1] ?? 0))) {
            prevK = k + 1;
        } else {
            prevK = k - 1;
        }
        const prevX = v[prevK + max] ?? 0;
        const prevY = prevX - prevK;
        while (x > prevX + 1 && y > prevY + 1) {
            ops.unshift({ type: "equal", text: a[x - 1] }); x--; y--;
        }
        if (d > 0) {
            if (x === prevX) {
                ops.unshift({ type: "insert", text: b[y - 1] }); y--;
            } else if (y === prevY) {
                ops.unshift({ type: "delete", text: a[x - 1] }); x--;
            }
        }
        while (x > prevX && y > prevY) {
            ops.unshift({ type: "equal", text: a[x - 1] }); x--; y--;
        }
        x = prevX; y = prevY;
    }
    return ops;
}

function renderWordDiff(aText: string, bText: string): { aHtml: string; bHtml: string } {
    const aWords = (aText || "").split(/(\s+)/);
    const bWords = (bText || "").split(/(\s+)/);
    const ops    = myersDiff(aWords, bWords);
    let aHtml = "", bHtml = "";
    for (const op of ops) {
        const esc = op.text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");
        if (op.type === "equal") {
            aHtml += esc; bHtml += esc;
        } else if (op.type === "delete") {
            aHtml += `<mark class="bg-red-500/30 text-red-300 rounded px-0.5">${esc}</mark>`;
        } else {
            bHtml += `<mark class="bg-green-500/30 text-green-300 rounded px-0.5">${esc}</mark>`;
        }
    }
    return { aHtml, bHtml };
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
