"use client";

import { useState, useEffect, useRef } from "react";
import { Download, Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import SkeletonCard from "@/components/SkeletonCard";

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

async function fetchSessions(): Promise<Session[]> {
    try {
        const res = await fetch("/api/sessions");
        const data = await res.json();
        return data.map((s: any) => ({
            ...s,
            sources: typeof s.sources === "string" ? JSON.parse(s.sources) : (s.sources ?? []),
        }));
    } catch { return []; }
}

async function createSession(session: Session): Promise<void> {
    await fetch("/api/sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(session),
    });
}

async function removeSession(id: string): Promise<void> {
    await fetch(`/api/sessions/${id}`, { method: "DELETE" });
}

function exportResult(result: QueryResponse, question: string) {
    const lines = [
        `# 查询结果`, ``,
        `**问题：** ${question}`, ``,
        `## 回答`, ``, result.answer, ``,
        `## 引用来源`, ``,
        ...result.sources.map(s =>
            `- **${s.doc_id} §${s.number}** ${s.title} （相关度 ${(s.score / 10).toFixed(2)}）`
        ),
        ``, `---`,
        `*导出时间：${new Date().toLocaleString("zh-CN")}*`,
    ];
    const blob = new Blob([lines.join("\n")], { type: "text/markdown;charset=utf-8" });
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
    const [streaming, setStreaming] = useState(false);
    const [result, setResult] = useState<QueryResponse | null>(null);
    const [sessions, setSessions] = useState<Session[]>([]);
    const [activeSession, setActiveSession] = useState<string | null>(null);
    const [rating, setRating] = useState<1 | -1 | null>(null);
    const answerRef = useRef("");

    useEffect(() => { fetchSessions().then(setSessions); }, []);

    async function handleQuery() {
        if (!query.trim()) return;
        setLoading(true);
        setResult(null);
        setRating(null);
        answerRef.current = "";

        try {
            const token = localStorage.getItem("token") ?? "";
            const res = await fetch("http://localhost:8000/api/query/stream", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${token}`,
                },
                body: JSON.stringify({ question: query, strategy }),
            });

            if (!res.ok) throw new Error("请求失败");

            setLoading(false);
            setStreaming(true);
            setResult({ answer: "", sources: [] });

            const reader = res.body!.getReader();
            const decoder = new TextDecoder();
            let sources: SourceSection[] = [];

            // 每100ms刷新一次UI显示流式内容
            const intervalId = setInterval(() => {
                setResult(prev => ({
                    answer: answerRef.current,
                    sources: prev?.sources ?? [],
                }));
            }, 100);

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                const lines = decoder.decode(value).split("\n");
                for (const line of lines) {
                    if (!line.startsWith("data: ")) continue;
                    const data = line.slice(6);
                    if (data === "[DONE]") break;
                    try {
                        const event = JSON.parse(data);
                        if (event.type === "sources") {
                            sources = event.content;
                            setResult(prev => ({ answer: prev?.answer ?? "", sources }));
                        } else if (event.type === "delta") {
                            answerRef.current += event.content;
                        }
                    } catch { }
                }
            }

            clearInterval(intervalId);
            setStreaming(false);

            const finalAnswer = answerRef.current;
            setResult({ answer: finalAnswer, sources });

            const session: Session = {
                id: Date.now().toString(),
                question: query,
                answer: finalAnswer,
                sources,
                timestamp: Date.now(),
            };
            await createSession(session);
            setActiveSession(session.id);
            fetchSessions().then(setSessions);

        } catch (e) {
            setLoading(false);
            setStreaming(false);
            setResult({ answer: e instanceof Error ? e.message : "网络异常", sources: [] });
        }
    }

    async function submitFeedback(r: 1 | -1) {
        if (!result) return;
        setRating(r);
        const stored = JSON.parse(localStorage.getItem("user") ?? "{}");
        await fetch("/api/feedback", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                question: query, answer: result.answer,
                sources: result.sources, rating: r,
                strategy, user_id: stored.user_id ?? "",
            }),
        });
    }

    function newSession() {
        setQuery(""); setResult(null); setActiveSession(null);
    }

    return (
        <div className="flex h-full bg-gray-950">

            {/* 左侧会话列表 */}
            <aside className="w-52 shrink-0 border-r border-gray-800 flex flex-col">
                <div className="px-4 py-3 border-b border-gray-800 flex items-center justify-between">
                    <div className="text-xs text-gray-500 uppercase tracking-wider">历史记录</div>
                    <button onClick={newSession}
                        className="inline-flex items-center gap-1 px-2 py-1 bg-indigo-600
                       text-white text-xs rounded hover:bg-indigo-500">
                        <Plus size={12} /> 新建
                    </button>
                </div>
                <div className="flex-1 overflow-auto px-2 py-2">
                    {sessions.length === 0 ? (
                        <div className="px-2 py-3 text-xs text-gray-600">暂无记录</div>
                    ) : sessions.map(session => (
                        <div key={session.id}
                            className={`group flex items-start gap-1 px-2 py-2 rounded-lg mb-0.5
                          cursor-pointer transition-colors ${activeSession === session.id ? "bg-gray-800" : "hover:bg-gray-900"
                                }`}
                            onClick={() => {
                                setQuery(session.question);
                                setResult({ answer: session.answer, sources: session.sources });
                                setActiveSession(session.id);
                            }}>
                            <span className="flex-1 text-xs text-gray-400 leading-relaxed line-clamp-2">
                                {session.question}
                            </span>
                            <button onClick={async e => {
                                e.stopPropagation();
                                await removeSession(session.id);
                                fetchSessions().then(setSessions);
                                if (activeSession === session.id) { setResult(null); setActiveSession(null); }
                            }} className="opacity-0 group-hover:opacity-100 flex-shrink-0
                             p-0.5 text-gray-600 hover:text-red-400 transition-all">
                                <Trash2 size={12} />
                            </button>
                        </div>
                    ))}
                </div>
            </aside>

            {/* 主区域 */}
            <div className="flex-1 overflow-auto">
                <div className="max-w-2xl mx-auto px-8 py-8">

                    <textarea value={query} onChange={e => setQuery(e.target.value)}
                        onKeyDown={e => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) handleQuery(); }}
                        placeholder="输入问题，例如：液压导管修理需要哪些工具？"
                        className="w-full h-24 px-4 py-3 bg-gray-900 border border-gray-700
                       rounded-xl text-gray-200 text-sm resize-none outline-none
                       focus:border-indigo-500 placeholder-gray-600 transition-colors" />

                    <div className="flex gap-2 mt-3 mb-4 flex-wrap">
                        {strategies.map(s => (
                            <button key={s.value} onClick={() => setStrategy(s.value)} title={s.desc}
                                className={`px-3 py-1.5 rounded-lg text-xs border transition-colors ${strategy === s.value
                                        ? "bg-indigo-600 border-indigo-600 text-white"
                                        : "border-gray-700 text-gray-400 hover:border-gray-500 hover:text-gray-300"
                                    }`}>
                                {s.label}
                            </button>
                        ))}
                    </div>

                    <div className="flex items-center gap-3 mb-8">
                        <button onClick={handleQuery} disabled={!query.trim() || loading || streaming}
                            className="px-5 py-2 bg-indigo-600 text-white text-sm rounded-lg
                         disabled:opacity-40 hover:bg-indigo-500 transition-colors">
                            {loading ? "检索中..." : streaming ? "生成中..." : "提交问题"}
                        </button>
                        <span className="text-xs text-gray-600">⌘ + Enter 快捷提交</span>
                        <button onClick={() => result && exportResult(result, query)}
                            disabled={!result || streaming}
                            className="ml-auto inline-flex items-center gap-1.5 px-2.5 py-1
                         bg-gray-800 text-gray-400 text-xs rounded hover:text-white
                         hover:bg-gray-700 transition-colors disabled:opacity-30 disabled:cursor-not-allowed">
                            <Download size={12} /> 导出 MD
                        </button>
                    </div>

                    {loading && <SkeletonCard />}

                    {(streaming || (!loading && result)) && result && (
                        <>
                            <div className="p-5 bg-gray-900 rounded-xl border border-gray-800 mb-4">
                                <div className="flex items-center justify-between mb-3">
                                    <div className="text-xs text-gray-500 uppercase tracking-wider">回答</div>
                                    {streaming && (
                                        <div className="flex items-center gap-1.5">
                                            <div className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-pulse" />
                                            <span className="text-xs text-indigo-400">生成中</span>
                                        </div>
                                    )}
                                </div>
                                <p className="text-gray-200 text-sm leading-relaxed whitespace-pre-wrap">
                                    {result.answer}
                                    {streaming && <span className="inline-block w-0.5 h-4 bg-indigo-400 ml-0.5 animate-pulse" />}
                                </p>
                                {!streaming && (
                                    <div className="flex items-center gap-3 mt-4 pt-4 border-t border-gray-700">
                                        <span className="text-xs text-gray-500">这个回答有帮助吗？</span>
                                        <button onClick={() => submitFeedback(1)}
                                            className={`px-3 py-1 rounded text-xs transition-colors ${rating === 1 ? "bg-green-600 text-white" : "bg-gray-800 text-gray-400 hover:text-green-400"
                                                }`}>
                                            👍 有帮助
                                        </button>
                                        <button onClick={() => submitFeedback(-1)}
                                            className={`px-3 py-1 rounded text-xs transition-colors ${rating === -1 ? "bg-red-600 text-white" : "bg-gray-800 text-gray-400 hover:text-red-400"
                                                }`}>
                                            👎 没帮助
                                        </button>
                                        {rating && <span className="text-xs text-gray-500">感谢反馈</span>}
                                    </div>
                                )}
                            </div>

                            {!streaming && result.sources.length > 0 && (
                                <div>
                                    <div className="text-xs text-gray-500 uppercase tracking-wider mb-2">
                                        引用来源 · {result.sources.length} 个章节
                                    </div>
                                    <div className="space-y-2">
                                        {result.sources.map(source => (
                                            <Link key={source.chunk_id} href={`/library/${source.doc_id}`}
                                                className="flex items-center justify-between px-4 py-3
                                   bg-gray-900 rounded-lg border border-gray-800
                                   hover:border-indigo-500 transition-colors cursor-pointer">
                                                <div>
                                                    <span className="text-xs font-mono text-indigo-400 mr-2">
                                                        {source.doc_id} §{source.number || source.chunk_id.split("_")[1]}
                                                    </span>
                                                    <span className="text-sm text-gray-300">{source.title}</span>
                                                </div>
                                                <span className="text-xs text-gray-600 flex-shrink-0 ml-4">
                                                    {(source.score / 10).toFixed(2)}
                                                </span>
                                            </Link>
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