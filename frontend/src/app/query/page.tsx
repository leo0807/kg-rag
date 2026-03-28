"use client";

import { useState, useEffect } from "react";
import { Download, Plus, Trash2 } from "lucide-react";
import { fetchApi, ApiError } from "@/lib/api";

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

interface Session {
    id: string;
    question: string;
    answer: string;
    sources: SourceSection[];
    timestamp: number;
}

type Strategy = "parallel" | "sequential" | "graph_augmented" | "multi_hop";

const strategies: { value: Strategy; label: string; desc: string }[] = [
    { value: "parallel", label: "并行检索", desc: "同时检索，RRF 融合" },
    { value: "sequential", label: "串行检索", desc: "图谱优先，精确查询" },
    { value: "graph_augmented", label: "图谱增强", desc: "向量召回+图谱扩展" },
    { value: "multi_hop", label: "多跳推理", desc: "复杂因果分析" },
];

function loadSessions(): Session[] {
    try {
        return JSON.parse(localStorage.getItem("query_sessions") ?? "[]");
    } catch { return []; }
}

function saveSession(session: Session) {
    const sessions = loadSessions();
    localStorage.setItem(
        "query_sessions",
        JSON.stringify([session, ...sessions].slice(0, 20))
    );
}

function deleteSession(id: string) {
    const sessions = loadSessions().filter(s => s.id !== id);
    localStorage.setItem("query_sessions", JSON.stringify(sessions));
}

function exportResult(result: QueryResponse, question: string) {
    const lines = [
        `# 查询结果`,
        ``,
        `**问题：** ${question}`,
        ``,
        `## 回答`,
        ``,
        result.answer,
        ``,
        `## 引用来源`,
        ``,
        ...result.sources.map(s =>
            `- **${s.doc_id} §${s.number}** ${s.title} （相关度 ${(s.score / 10).toFixed(2)}）`
        ),
        ``,
        `---`,
        `*导出时间：${new Date().toLocaleString("zh-CN")}*`,
    ];

    const content = lines.join("\n");
    const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `查询结果_${Date.now()}.md`;
    a.click();
    URL.revokeObjectURL(url);
}

export default function QueryPage() {
    const [query, setQuery] = useState("");
    const [strategy, setStrategy] = useState<Strategy>("parallel");
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState<QueryResponse | null>(null);
    const [sessions, setSessions] = useState<Session[]>([]);
    const [activeSession, setActiveSession] = useState<string | null>(null);

    useEffect(() => { setSessions(loadSessions()); }, []);

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

            const session: Session = {
                id: Date.now().toString(),
                question: query,
                answer: data.answer,
                sources: data.sources,
                timestamp: Date.now(),
            };

            setResult(data);
            saveSession(session);
            setActiveSession(session.id);
            setSessions(loadSessions());
        } catch (e) {
            const message = e instanceof ApiError ? e.message : "网络异常，请检查连接";
            setResult({ answer: message, sources: [] });
        } finally {
            setLoading(false);
        }
    }

    function newSession() {
        setQuery("");
        setResult(null);
        setActiveSession(null);
    }

    return (
        <div className="flex h-full bg-gray-950">

            {/* 左侧会话列表 */}
            <aside className="w-52 flex-shrink-0 border-r border-gray-800 flex flex-col">
                <div className="px-4 py-3 border-b border-gray-800 flex items-center justify-between">
                    <div className="text-xs text-gray-500 uppercase tracking-wider">
                        历史记录
                    </div>
                    <button
                        onClick={newSession}
                        className="inline-flex items-center gap-1 px-2 py-1 bg-indigo-600
                       text-white text-xs rounded hover:bg-indigo-500"
                    >
                        <Plus size={12} />
                        新建
                    </button>
                </div>

                <div className="flex-1 overflow-auto px-2 py-2">
                    {sessions.length === 0 ? (
                        <div className="px-2 py-3 text-xs text-gray-600">暂无记录</div>
                    ) : (
                        sessions.map(session => (
                            <div
                                key={session.id}
                                className={`group flex items-start gap-1 px-2 py-2 rounded-lg mb-0.5
                            cursor-pointer transition-colors ${activeSession === session.id
                                        ? "bg-gray-800"
                                        : "hover:bg-gray-900"
                                    }`}
                                onClick={() => {
                                    setQuery(session.question);
                                    setResult({ answer: session.answer, sources: session.sources });
                                    setActiveSession(session.id);
                                }}
                            >
                                <span className="flex-1 text-xs text-gray-400 leading-relaxed line-clamp-2">
                                    {session.question}
                                </span>
                                <button
                                    onClick={e => {
                                        e.stopPropagation();
                                        deleteSession(session.id);
                                        setSessions(loadSessions());
                                        if (activeSession === session.id) {
                                            setResult(null);
                                            setActiveSession(null);
                                        }
                                    }}
                                    className="opacity-0 group-hover:opacity-100 flex-shrink-0
                             p-0.5 text-gray-600 hover:text-red-400 transition-all"
                                >
                                    <Trash2 size={12} />
                                </button>
                            </div>
                        ))
                    )}
                </div>
            </aside>

            {/* 主区域 */}
            <div className="flex-1 overflow-auto">
                <div className="max-w-2xl mx-auto px-8 py-8">

                    <textarea
                        value={query}
                        onChange={e => setQuery(e.target.value)}
                        onKeyDown={e => {
                            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) handleQuery();
                        }}
                        placeholder="输入问题，例如：液压导管修理需要哪些工具？"
                        className="w-full h-24 px-4 py-3 bg-gray-900 border border-gray-700
                       rounded-xl text-gray-200 text-sm resize-none outline-none
                       focus:border-indigo-500 placeholder-gray-600 transition-colors"
                    />

                    <div className="flex gap-2 mt-3 mb-4 flex-wrap">
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

                        <button
                            onClick={() => result && exportResult(result, query)}
                            disabled={!result}
                            className="ml-auto inline-flex items-center gap-1.5 px-2.5 py-1
                         bg-gray-800 text-gray-400 text-xs rounded
                         hover:text-white hover:bg-gray-700 transition-colors
                         disabled:opacity-30 disabled:cursor-not-allowed"
                        >
                            <Download size={12} />
                            导出 MD
                        </button>
                    </div>

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

                            {result.sources.length > 0 && (
                                <div>
                                    <div className="text-xs text-gray-500 uppercase tracking-wider mb-2">
                                        引用来源 · {result.sources.length} 个章节
                                    </div>
                                    <div className="space-y-2">
                                        {result.sources.map(source => (
                                            <div
                                                key={source.chunk_id}
                                                className="flex items-center justify-between px-4 py-3
                                   bg-gray-900 rounded-lg border border-gray-800
                                   hover:border-gray-700 transition-colors"
                                            >
                                                <div>
                                                    <span className="text-xs font-mono text-indigo-400 mr-2">
                                                        {source.doc_id} §{source.number || source.chunk_id.split("_")[1]}
                                                    </span>
                                                    <span className="text-sm text-gray-300">{source.title}</span>
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