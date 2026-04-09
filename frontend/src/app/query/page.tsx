"use client";

import { useState, useRef, useEffect } from "react";
import { Download } from "lucide-react";
import SkeletonCard from "@/components/SkeletonCard";
import NetToast from "@/components/NetToast";
import type { NetToastType } from "@/components/NetToast";
import ConversationSidebar from "./ConversationSidebar";
import MessageBubble from "./MessageBubble";
import ConversationInput from "./ConversationInput";
import { useConversations } from "./useConversations";
import { useStreamQuery } from "./useStreamQuery";
import { SourceSection, Strategy } from "./types";
import { ReasoningChain } from "./ReasoningChain";
import { CausalChainPanel } from "./CausalChainPanel";

const SUGGESTED = [
    "液压导管修理需要什么工具",
    "CPS1220 的技术要求是什么",
    "收压接头的安装步骤有哪些",
];

const COUNTERFACTUAL_EXAMPLES = [
    "如果去掉热处理工序，铝合金零件还能满足强度要求吗？",
    "省略打孔前脱脂步骤，铆钉连接处是否仍满足密封标准？",
    "不用扭矩扳手装配螺栓，能否满足力矩要求？",
];

export default function QueryPage() {
    const {
        conversations, activeId, activeConv,
        setActiveId, createConversation,
        updateConversation, deleteConversation, clearConversation,
    } = useConversations();

    const [input,         setInput]         = useState("");
    const [strategy,      setStrategy]      = useState<Strategy>("parallel");
    const [pendingImages, setPendingImages] = useState<string[]>([]);
    const [quoteSource,   setQuoteSource]   = useState<SourceSection | null>(null);
    const [netToast, setNetToast] = useState<{ type: NetToastType; label: string } | null>(null);
    const bottomRef  = useRef<HTMLDivElement>(null);
    const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

    function showNetToast(type: NetToastType, label: string, autoDismissMs?: number) {
        if (toastTimer.current) clearTimeout(toastTimer.current);
        setNetToast({ type, label });
        if (autoDismissMs) toastTimer.current = setTimeout(() => setNetToast(null), autoDismissMs);
    }

    const {
        loading, streaming, streamingMsgId, reasoningSteps, causalChain, submit,
    } = useStreamQuery({ strategy, activeId, activeConv, conversations, createConversation, updateConversation, showNetToast });

    // Refs for visibility change callback
    const activeIdRef      = useRef<string | null>(activeId);
    const conversationsRef = useRef(conversations);
    const deleteConvRef    = useRef(deleteConversation);
    useEffect(() => { activeIdRef.current      = activeId;          });
    useEffect(() => { conversationsRef.current = conversations;     });
    useEffect(() => { deleteConvRef.current    = deleteConversation; });

    useEffect(() => {
        const handleVisibility = () => {
            if (document.visibilityState !== "visible") return;
            const cid  = activeIdRef.current;
            if (!cid) return;
            const conv = conversationsRef.current.find(c => c.id === cid);
            if (conv && conv.messages.length === 0) deleteConvRef.current(cid);
        };
        document.addEventListener("visibilitychange", handleVisibility);
        return () => document.removeEventListener("visibilitychange", handleVisibility);
    }, []);

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [activeConv?.messages.length, streaming]);

    useEffect(() => {
        const handleOffline = () => showNetToast("offline", "网络已断开");
        const handleOnline  = () => showNetToast("online",  "网络已恢复", 3000);
        window.addEventListener("offline", handleOffline);
        window.addEventListener("online",  handleOnline);
        return () => { window.removeEventListener("offline", handleOffline); window.removeEventListener("online", handleOnline); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    async function handleSubmit() {
        if ((!input.trim() && pendingImages.length === 0) || loading || streaming) return;
        const citation = quoteSource
            ? `> 引用章节：${quoteSource.doc_id} §${quoteSource.number}《${quoteSource.title}》\n\n`
            : "";
        const question = citation + input.trim();
        const images   = [...pendingImages];
        setInput(""); setPendingImages([]); setQuoteSource(null);
        await submit(question, images);
    }

    async function handleBranch(upToIndex: number) {
        if (!activeConv) return;
        const branchedMessages = activeConv.messages.slice(0, upToIndex + 1);
        const branchTitle = `分支: ${branchedMessages[0]?.content?.slice(0, 18) || "新分支"}`;
        const token = localStorage.getItem("token") || "";
        try {
            const res = await fetch("/api/conversations", {
                method: "POST",
                headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` },
                body: JSON.stringify({ title: branchTitle, strategy, messages: branchedMessages }),
            });
            const conv = await res.json();
            if (conv?.id) setActiveId(conv.id);
        } catch (e) { console.error("分支创建失败:", e); }
    }

    async function handleSourceClick(chunkId: string) {
        const stored   = JSON.parse(localStorage.getItem("user") ?? "{}");
        const lastUser = activeConv?.messages.findLast(m => m.role === "user");
        const lastAI   = activeConv?.messages.findLast(m => m.role === "assistant");
        await fetch("/api/feedback", {
            method:  "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                question: lastUser?.content ?? "", answer: lastAI?.content ?? "",
                sources: [], rating: 1, strategy, user_id: stored.user_id ?? "",
                detail: `clicked_source:${chunkId}`,
            }),
        });
    }

    function handleQuoteSource(source: SourceSection) {
        setQuoteSource(source);
        handleSourceClick(source.chunk_id);
    }

    function exportConversation() {
        if (!activeConv || activeConv.messages.length === 0) return;
        const lines = [`# ${activeConv.title}`, ``,
            ...activeConv.messages.flatMap(m => [
                m.role === "user" ? `**用户：** ${m.content}` : `**AI：** ${m.content}`, ``,
            ]),
            `---`, `*导出时间：${new Date().toLocaleString("zh-CN")}*`,
        ];
        const blob = new Blob([lines.join("\n")], { type: "text/markdown;charset=utf-8" });
        const a = document.createElement("a"); a.href = URL.createObjectURL(blob);
        a.download = `${activeConv.title}_${Date.now()}.md`; a.click();
    }

    const historyLen = activeConv?.messages.length ?? 0;

    return (
        <div className="flex h-full bg-gray-950">
            {netToast && <NetToast type={netToast.type} label={netToast.label} onClose={() => setNetToast(null)} />}
            <ConversationSidebar
                conversations={conversations} activeId={activeId}
                onSelect={setActiveId} onDelete={deleteConversation}
                onNew={() => createConversation()}
                disableNew={activeConv !== null && activeConv.messages.length === 0}
            />

            <div className="flex-1 flex flex-col min-w-0">
                <div className="flex items-center justify-between px-6 py-3 border-b border-gray-800 shrink-0">
                    <div className="text-sm text-gray-400 truncate">{activeConv?.title ?? "选择或新建对话"}</div>
                    <button onClick={exportConversation} disabled={!activeConv || historyLen === 0}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs text-gray-500 hover:text-gray-300 border border-gray-800 hover:border-gray-600 rounded-lg transition-colors disabled:opacity-30">
                        <Download size={12} /> 导出对话
                    </button>
                </div>

                <div className="flex-1 overflow-auto px-4 py-6">
                    <div className="max-w-3xl mx-auto">
                        {!activeConv || historyLen === 0 ? (
                            <div className="flex flex-col items-center justify-center min-h-64 gap-5 py-10">
                                <div className="text-5xl">✈️</div>
                                <div className="text-gray-500 text-sm">开始提问关于航空工艺规范的问题</div>
                                <div className="flex flex-wrap gap-2 justify-center">
                                    {SUGGESTED.map(q => (
                                        <button key={q} onClick={() => setInput(q)}
                                            className="px-3 py-1.5 bg-gray-900 border border-gray-700 text-xs text-gray-400 rounded-xl hover:border-indigo-500 hover:text-white transition-colors">
                                            {q}
                                        </button>
                                    ))}
                                </div>
                                <div className="w-full max-w-md">
                                    <div className="flex items-center gap-2 mb-2">
                                        <span className="text-xs text-amber-600 font-medium">反事实假设推理示例</span>
                                        <span className="text-xs text-gray-600">— 选择"反事实"策略后尝试</span>
                                    </div>
                                    <div className="flex flex-col gap-1.5">
                                        {COUNTERFACTUAL_EXAMPLES.map(q => (
                                            <button key={q}
                                                onClick={() => { setInput(q); setStrategy("counterfactual"); }}
                                                className="px-3 py-2 bg-amber-950/20 border border-amber-800/30 text-xs text-amber-400/80 rounded-xl text-left hover:border-amber-600/50 hover:text-amber-300 transition-colors">
                                                {q}
                                            </button>
                                        ))}
                                    </div>
                                </div>
                            </div>
                        ) : (
                            <>
                                <ReasoningChain steps={reasoningSteps} />
                                {activeConv.messages.map((msg, i) => (
                                    <div key={msg.id}>
                                        {msg.role === "assistant" && (
                                            msg.causalChain
                                                ? <CausalChainPanel data={msg.causalChain} />
                                                : streaming && msg.id === streamingMsgId && causalChain
                                                    ? <CausalChainPanel data={causalChain} />
                                                    : null
                                        )}
                                        <MessageBubble
                                            role={msg.role} content={msg.content}
                                            sources={msg.sources} images={msg.images}
                                            streaming={streaming && msg.id === streamingMsgId}
                                            onSourceClick={handleSourceClick}
                                            onQuoteSource={handleQuoteSource}
                                            onBranch={msg.role === "assistant" && !streaming ? () => handleBranch(i) : undefined}
                                        />
                                    </div>
                                ))}
                            </>
                        )}
                        {loading && <SkeletonCard />}
                        <div ref={bottomRef} />
                    </div>
                </div>

                <ConversationInput
                    value={input} strategy={strategy} loading={loading} streaming={streaming}
                    historyLen={historyLen} pendingImages={pendingImages} quoteSource={quoteSource}
                    onChange={setInput} onStrategy={setStrategy} onSubmit={handleSubmit}
                    onClear={clearConversation}
                    onAddImages={imgs => setPendingImages(prev => [...prev, ...imgs])}
                    onRemoveImage={idx => setPendingImages(prev => prev.filter((_, i) => i !== idx))}
                    onClearQuote={() => setQuoteSource(null)}
                />
            </div>
        </div>
    );
}
