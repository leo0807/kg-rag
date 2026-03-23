"use client";

import { useState } from "react";

interface QueryResponse {
    answer: string;
    strategy: string;
    confidence: number;
    sources: { chunk_id: string; section_title: string; content: string }[];
}

export default function QueryPage() {
    const [query, setQuery] = useState("");
    const [loading, setLoading] = useState(false);
    const [answer, setAnswer] = useState<string | null>(null);

    async function handleQuery() {
        if (!query.trim()) return;
        setLoading(true);
        setAnswer(null);

        try {
            const res = await fetch("http:localhost:8000/api/query", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ query, strategy: "parallel" }),
            });
            const data = await res.json() as QueryResponse;
            setAnswer(data.answer);
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

            <button
                onClick={handleQuery}
                disabled={!query.trim() || loading}
                className="mt-3 px-5 py-2 bg-indigo-600 text-white text-sm
                   rounded-lg disabled:opacity-50 hover:bg-indigo-500"
            >
                {loading ? "查询中..." : "提交问题"}
            </button>

            {answer && (
                <div className="mt-6 p-4 bg-gray-900 rounded-lg border border-gray-800">
                    <div className="text-xs text-gray-500 mb-2">回答</div>
                    <p className="text-gray-200 text-sm leading-relaxed">{answer}</p>
                </div>
            )}
        </div>
    )
}