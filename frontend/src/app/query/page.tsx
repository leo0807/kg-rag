"use client";

import { useState } from "react";

interface QueryResponse {
    answer: string;
    sources: {
        chunk_id: string;
        doc_id: string;
        number: string;
        title: string;
        score: number;
    }[];
}

type Strategy = "parallel" | "sequential" | "graph_augmented" | "multi_hop";

export default function QueryPage() {
    const [query, setQuery] = useState("");
    const [loading, setLoading] = useState(false);
    const [answer, setAnswer] = useState<string | null>(null);
    const [strategy, setStrategy] = useState<Strategy>("parallel");
    const [result, setResult] = useState<QueryResponse | null>(null);

    const strategies: { value: Strategy; label: string }[] = [
        { value: "parallel", label: "并行检索" },
        { value: "sequential", label: "串行检索" },
        { value: "graph_augmented", label: "图谱增强" },
        { value: "multi_hop", label: "多跳推理" },
    ];

    async function handleQuery() {
        if (!query.trim()) return;
        setLoading(true);
        setAnswer(null);

        try {
            const res = await fetch("/api/query", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ question: query, strategy }),
            });
            const data = await res.json() as QueryResponse;
            setResult(data);
        } catch (error) {
            setAnswer("请求失败，检查后段服务");
        } finally {
            setLoading(false);
        }
    }

    return (
        <div className="p-8 max-w-3xl">
            <h1 className="text-2xl font-semibold text-white mb-6">智能问答</h1>

            <textarea
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="输入问题，例如：液压导管修理需要哪些工具？"
                className="w-full h-28 px-4 py-3 bg-gray-900 border border-gray-700
                   rounded-lg text-gray-200 text-sm resize-none outline-none
                   focus:border-indigo-500 placeholder-gray-600"
            />
            <div className="mt-3 flex gap-2">
                {strategies.map(({ value, label }) => (
                    <button
                        key={value}
                        onClick={() => setStrategy(value)}
                        className={`px-3 py-1.5 rounded-md text-xs border transition-colors ${strategy === value
                            ? "bg-indigo-600 border-indigo-600 text-white"
                            : "border-gray-700 text-gray-400 hover:border-gray-500"
                            }`}
                    >
                        {label}
                    </button>
                ))}
            </div>
            <button
                onClick={handleQuery}
                disabled={!query.trim() || loading}
                className="mt-3 px-5 py-2 bg-indigo-600 text-white text-sm
                   rounded-lg disabled:opacity-50 hover:bg-indigo-500"
            >
                {loading ? "查询中..." : "提交问题"}
            </button>

            {result && (
                <div className="mt-6 p-4 bg-gray-900 rounded-lg border border-gray-800">
                    <div className="text-xs text-gray-500 mb-2">回答</div>
                    <p className="text-gray-200 text-sm leading-relaxed">{result.answer}</p>
                </div>
            )}
            {result && result.sources.length > 0 && (
                <div className="mt-4">
                    <div className="text-xs text-gray-500 mb-2">
                        引用来源 · {result.sources.length} 个章节
                    </div>
                    <div className="space-y-2">
                        {result.sources.map((source) => (
                            <div
                                key={source.chunk_id}
                                className="px-4 py-3 bg-gray-900 rounded-lg border border-gray-800"
                            >
                                <div className="flex items-center justify-between mb-1">
                                    <span className="text-xs font-mono text-indigo-400">
                                        {source.doc_id} §{source.number || source.chunk_id.split("_")[1]}
                                    </span>
                                    <span className="text-xs text-gray-600">
                                        相关度 {(source.score / 10).toFixed(2)}
                                    </span>
                                </div>
                                <div className="text-sm text-gray-300">{source.title}</div>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    )
}