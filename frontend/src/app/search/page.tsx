"use client";

import { useState } from "react";
import Link from "next/link";
import { Search } from "lucide-react";

interface SearchResult {
    chunk_id: string;
    doc_id: string;
    number: string;
    title: string;
    snippet: string;
    score: number;
    highlight?: Record<string, string[]>;
}

export default function SearchPage() {
    const [query, setQuery] = useState("");
    const [results, setResults] = useState<SearchResult[]>([]);
    const [loading, setLoading] = useState(false);
    const [total, setTotal] = useState(0);

    async function handleSearch() {
        if (!query.trim()) return;
        setLoading(true);
        try {
            const res = await fetch(
                `/api/search?q=${encodeURIComponent(query)}&top_k=20`
            );
            const data = await res.json();
            setResults(data.results);
            setTotal(data.total);
        } finally {
            setLoading(false);
        }
    }

    function renderHighlight(result: SearchResult) {
        if (result.highlight?.content?.[0]) {
            return result.highlight.content[0];
        }
        return result.snippet;
    }

    return (
        <div className="p-8 max-w-3xl mx-auto">
            <h1 className="text-2xl font-semibold text-white mb-6">全局搜索</h1>

            <div className="flex gap-2 mb-6">
                <div className="relative flex-1">
                    <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
                    <input
                        value={query}
                        onChange={e => setQuery(e.target.value)}
                        onKeyDown={e => e.key === "Enter" && handleSearch()}
                        placeholder="搜索章节内容，支持中文关键词..."
                        className="w-full pl-9 pr-4 py-2.5 bg-gray-900 border border-gray-700
                       rounded-xl text-gray-200 text-sm outline-none
                       focus:border-indigo-500 placeholder-gray-600"
                    />
                </div>
                <button
                    onClick={handleSearch}
                    disabled={!query.trim() || loading}
                    className="px-5 py-2.5 bg-indigo-600 text-white text-sm rounded-xl
                     hover:bg-indigo-500 disabled:opacity-40"
                >
                    {loading ? "搜索中..." : "搜索"}
                </button>
            </div>

            {total > 0 && (
                <div className="text-xs text-gray-500 mb-4">
                    找到 {total} 个相关章节
                </div>
            )}

            <div className="space-y-3">
                {results.map(result => (
                    <Link
                        key={result.chunk_id}
                        href={`/library/${result.doc_id}`}
                        className="block p-4 bg-gray-900 rounded-xl border border-gray-800
                       hover:border-indigo-500 transition-colors"
                    >
                        <div className="flex items-center justify-between mb-2">
                            <div className="flex items-center gap-2">
                                <span className="text-xs font-mono text-indigo-400">
                                    {result.doc_id}
                                </span>
                                {result.number && (
                                    <span className="text-xs text-gray-500">§{result.number}</span>
                                )}
                                <span className="text-sm text-gray-200 font-medium">
                                    {result.title}
                                </span>
                            </div>
                            <span className="text-xs text-gray-600">
                                {result.score.toFixed(2)}
                            </span>
                        </div>
                        <div
                            className="text-xs text-gray-400 leading-relaxed line-clamp-3"
                            dangerouslySetInnerHTML={{
                                __html: renderHighlight(result)
                                    .replace(/<mark>/g, '<mark class="bg-indigo-500/30 text-indigo-300 rounded px-0.5">')
                            }}
                        />
                    </Link>
                ))}
            </div>
        </div>
    );
}