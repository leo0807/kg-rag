"use client";

import { fetchApi, ApiError } from "@/lib/api";
import { useState, useEffect } from "react";

interface HistoryItem {
    question: string;
    timestamp: number;
}

interface SourceSection {
    chunk_id: string;
    doc_id: string;
    number: string;
    title: string;
    score: number;
}

interface QueryResponse {
    answer: string;
    sources: SourceSection[];
}

type Strategy = "parallel" | "sequential" | "graph_augmented" | "multi_hop";

const strategies: { value: Strategy; label: string; desc: string }[] = [
    { value: "parallel", label: "并行检索", desc: "同时检索，RRF 融合" },
    { value: "sequential", label: "串行检索", desc: "图谱优先，精确查询" },
    { value: "graph_augmented", label: "图谱增强", desc: "向量召回+图谱扩展" },
    { value: "multi_hop", label: "多跳推理", desc: "复杂因果分析" },
];

function loadHistory(): HistoryItem[] {
    try {
        return JSON.parse(localStorage.getItem("query_history") ?? "[]");
    } catch { return []; }
}

function saveHistory(question: string) {
    const history = loadHistory();
    const updated = [
        { question, timestamp: Date.now() },
        ...history.filter(h => h.question !== question),
    ].slice(0, 10);
    localStorage.setItem("query_history", JSON.stringify(updated));
}

export default function QueryPage() {
    const [query, setQuery] = useState("");
    const [strategy, setStrategy] = useState<Strategy>("parallel");
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState<QueryResponse | null>(null);
    const [history, setHistory] = useState<HistoryItem[]>([]);

    useEffect(() => { setHistory(loadHistory()); }, []);

    async function handleQuery() {
        if (!query.trim()) return;
        setLoading(true);
        setResult(null);
        try {
            const data = await fetchApi<QueryResponse>("/api/query", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ question: query, strategy }),
            });
            setResult(data);
            saveHistory(query);
            setHistory(loadHistory());
        } catch (e) {
            const message = e instanceof ApiError
                ? e.message
                : "网络异常，请检查连接";
            setResult({ answer: message, sources: [] });
        } finally {
            setLoading(false);
        }
    }



    return (
        <div className="flex h-full bg-gray-950">

            {/* 左侧历史记录 */}
            <aside className="w-52 flex-shrink-0 border-r border-gray-800 flex flex-col">
                <div className="px-4 py-4 border-b border-gray-800">
                    <div className="text-xs text-gray-500 uppercase tracking-wider">
                        查询历史
                    </div>
                </div>
                <div className="flex-1 overflow-auto px-2 py-2">
                    {history.length === 0 ? (
                        <div className="px-2 py-3 text-xs text-gray-600">暂无记录</div>
                    ) : (
                        history.map(item => (
                            <button
                                key={item.timestamp}
                                onClick={() => setQuery(item.question)}
                                className="w-full text-left px-3 py-2.5 rounded-lg text-xs
                           text-gray-400 hover:text-white hover:bg-gray-800
                           transition-colors mb-0.5 leading-relaxed"
                            >
                                {item.question}
                            </button>
                        ))
                    )}
                </div>
            </aside>

            {/* 主区域 */}
            <div className="flex-1 overflow-auto">
                <div className="max-w-2xl mx-auto px-8 py-8">

                    {/* 输入区 */}
                    <div className="mb-4">
                        <textarea
                            value={query}
                            onChange={e => setQuery(e.target.value)}
                            onKeyDown={e => {
                                if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                                    e.preventDefault();
                                    handleQuery();
                                }
                            }}
                            placeholder="输入问题，例如：液压导管修理需要哪些工具？"
                            className="w-full h-24 px-4 py-3 bg-gray-900 border border-gray-700
                         rounded-xl text-gray-200 text-sm resize-none outline-none
                         focus:border-indigo-500 placeholder-gray-600
                         transition-colors"
                        />
                    </div>

                    {/* 策略选择 */}
                    <div className="flex gap-2 mb-4 flex-wrap">
                        {strategies.map(s => (
                            <button
                                key={s.value}
                                onClick={() => setStrategy(s.value)}
                                title={s.desc}
                                className={`px-3 py-1.5 rounded-lg text-xs border transition-colors ${strategy === s.value
                                    ? "bg-indigo-600 border-indigo-600 text-white"
                                    : "border-gray-700 text-gray-400 hover:border-gray-500 hover:text-gray-300"
                                    }`}
                            >
                                {s.label}
                            </button>
                        ))}
                    </div>

                    {/* 提交按钮 */}
                    <div className="flex items-center gap-3 mb-8">
                        <button
                            onClick={handleQuery}
                            disabled={!query.trim() || loading}
                            className="px-5 py-2 bg-indigo-600 text-white text-sm rounded-lg
                         disabled:opacity-40 hover:bg-indigo-500 transition-colors"
                        >
                            {loading ? "检索中..." : "提交问题"}
                        </button>
                        <span className="text-xs text-gray-600">⌘ + Enter 快捷提交</span>
                    </div>

                    {/* 回答 */}
                    {result && (
                        <>
                            <div className="p-5 bg-gray-900 rounded-xl border border-gray-800 mb-4">
                                <div className="text-xs text-gray-500 mb-3 uppercase tracking-wider">
                                    回答
                                </div>
                                <p className="text-gray-200 text-sm leading-relaxed whitespace-pre-wrap">
                                    {result.answer}
                                </p>
                            </div>

                            {/* 来源列表 */}
                            {result.sources.length > 0 && (
                                <div>
                                    <div className="text-xs text-gray-500 uppercase tracking-wider mb-2">
                                        引用来源 · {result.sources.length} 个章节
                                    </div>
                                    <div className="space-y-2">
                                        {result.sources.map(source => (
                                            <div
                                                key={source.chunk_id}
                                                className="flex items-center justify-between
                                   px-4 py-3 bg-gray-900 rounded-lg
                                   border border-gray-800 hover:border-gray-700
                                   transition-colors"
                                            >
                                                <div>
                                                    <span className="text-xs font-mono text-indigo-400 mr-2">
                                                        {source.doc_id} §{source.number || source.chunk_id.split("_")[1]}
                                                    </span>
                                                    <span className="text-sm text-gray-300">
                                                        {source.title}
                                                    </span>
                                                </div>
                                                <span className="text-xs text-gray-600 flex-shrink-0 ml-4">
                                                    {(source.score / 10).toFixed(2)}
                                                </span>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </>
                    )}
                </div>
            </div>
        </div>
    );
}