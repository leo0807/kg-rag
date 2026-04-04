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
import { Message, SourceSection, Strategy, CausalChainData } from "./types";

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

// ── 多跳推理链路展示组件 ───────────────────────────────────────────────────────
interface ReasoningStep {
    hop: number;
    query: string;
    found: number;
    titles: string[];
}

function ReasoningChain({ steps }: { steps: ReasoningStep[] }) {
    const [open, setOpen] = useState(false);
    if (!steps.length) return null;
    return (
        <div className="mb-4 border border-gray-800 rounded-xl overflow-hidden">
            <button onClick={() => setOpen(v => !v)}
                className="w-full flex items-center gap-2 px-4 py-2.5 bg-gray-900 text-left hover:bg-gray-800/50 transition-colors">
                <svg className={`w-3 h-3 transition-transform text-gray-500 ${open ? "rotate-90" : ""}`}
                    viewBox="0 0 12 12" fill="currentColor"><path d="M4 2l5 4-5 4V2z" /></svg>
                <span className="text-xs text-gray-500">多跳推理过程</span>
                <span className="ml-auto text-xs text-gray-600">{steps.length} 跳</span>
            </button>
            {open && (
                <div className="px-4 py-3 space-y-3 bg-gray-950">
                    {steps.map(step => (
                        <div key={step.hop} className="flex gap-3">
                            <div className="w-5 h-5 rounded-full bg-indigo-900 border border-indigo-700
                                            flex items-center justify-center text-xs text-indigo-400 shrink-0">
                                {step.hop}
                            </div>
                            <div>
                                <div className="text-xs text-gray-300 font-medium">{step.query}</div>
                                <div className="text-xs text-gray-600 mt-0.5">找到 {step.found} 个章节</div>
                                {step.titles.length > 0 && (
                                    <div className="flex flex-wrap gap-1 mt-1">
                                        {step.titles.map((t, i) => (
                                            <span key={i} className="text-xs bg-gray-800 text-gray-400 px-1.5 py-0.5 rounded">
                                                {t.length > 30 ? t.slice(0, 30) + "…" : t}
                                            </span>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}

// ── 反事实因果链展示组件 ──────────────────────────────────────────────────────
function CausalChainPanel({ data }: { data: CausalChainData }) {
    const [open, setOpen] = useState(true);
    const intent = data.intent;
    const typeLabel: Record<string, string> = {
        Process: "工序", Tool: "工具", Material: "材料", Constraint: "约束",
    };

    return (
        <div className="mb-4 border border-amber-800/40 rounded-xl overflow-hidden bg-amber-950/10">
            <button
                onClick={() => setOpen(v => !v)}
                className="w-full flex items-center gap-2 px-4 py-2.5 text-left hover:bg-amber-900/10 transition-colors"
            >
                <svg className={`w-3 h-3 transition-transform text-amber-500 ${open ? "rotate-90" : ""}`}
                    viewBox="0 0 12 12" fill="currentColor"><path d="M4 2l5 4-5 4V2z" /></svg>
                <span className="text-xs text-amber-400 font-medium">反事实因果链分析</span>
                {intent.removed_name && (
                    <span className="ml-1 px-1.5 py-0.5 bg-amber-800/30 text-amber-300 text-xs rounded">
                        去掉：{intent.removed_name}
                    </span>
                )}
                <span className="ml-auto text-xs text-amber-700">
                    {data.affected_sections.length} 个受影响章节
                </span>
            </button>

            {open && (
                <div className="px-4 pb-4 space-y-3">
                    {/* 意图摘要 */}
                    <div className="flex flex-wrap gap-2 pt-1 text-xs">
                        {intent.removed_name && (
                            <span className="px-2 py-1 bg-red-900/30 border border-red-800/40 text-red-400 rounded-lg">
                                ❌ 移除 {typeLabel[intent.removed_type] || ""} · {intent.removed_name}
                            </span>
                        )}
                        {intent.subject && (
                            <span className="px-2 py-1 bg-gray-800 text-gray-400 rounded-lg">
                                主体：{intent.subject}
                            </span>
                        )}
                        {intent.requirement && (
                            <span className="px-2 py-1 bg-gray-800 text-gray-400 rounded-lg">
                                目标：{intent.requirement}
                            </span>
                        )}
                    </div>

                    {/* 受影响章节 + 约束 */}
                    {data.affected_sections.length > 0 && (
                        <div>
                            <div className="text-xs text-gray-500 mb-1.5">受影响章节与约束</div>
                            <div className="space-y-1.5">
                                {data.affected_sections.slice(0, 5).map(sec => (
                                    <div key={sec.chunk_id}
                                        className="flex items-start gap-2 bg-gray-900/60 rounded-lg px-3 py-2">
                                        <span className="text-xs text-amber-600 shrink-0 mt-0.5">⚠</span>
                                        <div className="min-w-0">
                                            <span className="text-xs text-indigo-400 font-mono mr-1">
                                                {sec.doc_id} §{sec.number}
                                            </span>
                                            <span className="text-xs text-gray-300">{sec.title}</span>
                                            {sec.constraints.length > 0 && (
                                                <div className="flex flex-wrap gap-1 mt-1">
                                                    {sec.constraints.slice(0, 3).map((c, i) => (
                                                        <span key={i}
                                                            className="text-xs bg-amber-900/20 border border-amber-800/30 text-amber-400 px-1.5 py-0.5 rounded">
                                                            {(c.description || c.type || "").trim()}
                                                            {c.value && ` ${c.value}${c.value_max ? "~" + c.value_max : ""} ${c.unit || ""}`.trim()}
                                                        </span>
                                                    ))}
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* 替代方案 */}
                    <div>
                        <div className="text-xs text-gray-500 mb-1.5">替代方案</div>
                        {data.alternatives.length > 0 ? (
                            <div className="flex flex-wrap gap-1.5">
                                {data.alternatives.map((alt, i) => (
                                    <span key={i}
                                        className="text-xs bg-emerald-900/20 border border-emerald-800/30 text-emerald-400 px-2 py-0.5 rounded-lg">
                                        ✓ {alt}
                                    </span>
                                ))}
                            </div>
                        ) : (
                            <span className="text-xs text-gray-600">图谱中未发现已知替代方案</span>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}

export default function QueryPage() {
    const {
        conversations, activeId, activeConv,
        setActiveId, createConversation,
        updateConversation, deleteConversation, clearConversation,
    } = useConversations();

    const [input,          setInput]          = useState("");
    const [strategy,       setStrategy]       = useState<Strategy>("parallel");
    const [loading,        setLoading]        = useState(false);
    const [streaming,      setStreaming]      = useState(false);
    const [streamingMsgId, setStreamingMsgId] = useState<string | null>(null);
    const [pendingImages,  setPendingImages]  = useState<string[]>([]);
    const [reasoningSteps, setReasoningSteps] = useState<ReasoningStep[]>([]);
    const [causalChain,    setCausalChain]    = useState<CausalChainData | null>(null);
    const [netToast, setNetToast] = useState<{ type: NetToastType; label: string } | null>(null);
    const answerRef    = useRef("");
    const bottomRef    = useRef<HTMLDivElement>(null);
    const toastTimer   = useRef<ReturnType<typeof setTimeout> | null>(null);

    function showNetToast(type: NetToastType, label: string, autoDismissMs?: number) {
        if (toastTimer.current) clearTimeout(toastTimer.current);
        setNetToast({ type, label });
        if (autoDismissMs) {
            toastTimer.current = setTimeout(() => setNetToast(null), autoDismissMs);
        }
    }

    // Refs 用于在 visibilitychange 回调中读取最新值，避免闭包过期
    const activeIdRef       = useRef<string | null>(activeId);
    const conversationsRef  = useRef(conversations);
    const deleteConvRef     = useRef(deleteConversation);
    useEffect(() => { activeIdRef.current      = activeId;         });
    useEffect(() => { conversationsRef.current = conversations;    });
    useEffect(() => { deleteConvRef.current    = deleteConversation; });

    // 切换浏览器 tab 返回时，若当前对话为空则删除
    useEffect(() => {
        const handleVisibility = () => {
            if (document.visibilityState !== "visible") return;
            const cid = activeIdRef.current;
            if (!cid) return;
            const conv = conversationsRef.current.find(c => c.id === cid);
            if (conv && conv.messages.length === 0) {
                deleteConvRef.current(cid);
            }
        };
        document.addEventListener("visibilitychange", handleVisibility);
        return () => document.removeEventListener("visibilitychange", handleVisibility);
    }, []);

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [activeConv?.messages.length, streaming]);

    // 网络在线/离线检测
    useEffect(() => {
        const handleOffline = () => showNetToast("offline", "网络已断开");
        const handleOnline  = () => showNetToast("online",  "网络已恢复", 3000);
        window.addEventListener("offline", handleOffline);
        window.addEventListener("online",  handleOnline);
        return () => {
            window.removeEventListener("offline", handleOffline);
            window.removeEventListener("online",  handleOnline);
        };
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    async function handleSubmit() {
        if ((!input.trim() && pendingImages.length === 0) || loading || streaming) return;

        const question = input.trim();
        const images   = [...pendingImages];
        setInput("");
        setPendingImages([]);
        setReasoningSteps([]);
        setCausalChain(null);

        let convId = activeId;
        if (!convId) {
            convId = await createConversation(question.slice(0, 20), strategy);
        }

        const conv     = conversations.find(c => c.id === convId);
        const prevMsgs = conv?.messages ?? [];

        const userMsg: Message = {
            id:        `user_${Date.now()}`,
            role:      "user",
            content:   question,
            images:    images.length > 0 ? images : undefined,
            timestamp: Date.now(),
        };
        const aiMsgId = `ai_${Date.now()}`;
        const aiMsg: Message = {
            id: aiMsgId, role: "assistant", content: "", sources: [], timestamp: Date.now(),
        };

        const newMsgs  = [...prevMsgs, userMsg, aiMsg];
        const newTitle = prevMsgs.length === 0 ? question.slice(0, 20) : undefined;
        await updateConversation(convId, newMsgs, newTitle);

        setStreamingMsgId(aiMsgId);
        setLoading(true);
        answerRef.current = "";

        const history = (activeConv?.messages ?? []).map(m => ({ role: m.role, content: m.content }));

        // 定期将流式内容写入对话记录
        const intervalId = setInterval(() => {
            updateConversation(convId!, newMsgs.map(m =>
                m.id === aiMsgId ? { ...m, content: answerRef.current } : m
            ));
        }, 150);

        let sources: SourceSection[] = [];
        let streamCausalChain: CausalChainData | null = null;

        // SSE 流读取 + 指数退避重连
        const MAX_RETRIES = 3;
        let retryDelay    = 1000;

        try {
            for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
                if (attempt > 0) {
                    showNetToast("reconnecting", `连接中断，${retryDelay / 1000}s 后重试 (${attempt}/${MAX_RETRIES})…`);
                    await new Promise(r => setTimeout(r, retryDelay));
                    retryDelay = Math.min(retryDelay * 2, 8000);
                    answerRef.current = ""; // 重置内容，重新生成
                    showNetToast("reconnecting", "正在重连…");
                }

                let streamDone = false;
                try {
                    const token = localStorage.getItem("token") ?? "";
                    const res = await fetch("http://localhost:8000/api/query/stream", {
                        method:  "POST",
                        headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` },
                        body:    JSON.stringify({ question, strategy, history, images }),
                    });
                    if (!res.ok) throw new Error("请求失败");

                    if (attempt === 0) {
                        setLoading(false);
                        setStreaming(true);
                    } else {
                        showNetToast("online", "已重连", 3000);
                    }

                    const reader  = res.body!.getReader();
                    const decoder = new TextDecoder();

                    while (true) {
                        const { done, value } = await reader.read();
                        if (done) break;
                        for (const line of decoder.decode(value).split("\n")) {
                            if (!line.startsWith("data: ")) continue;
                            const data = line.slice(6);
                            if (data === "[DONE]") break;
                            try {
                                const event = JSON.parse(data);
                                if (event.type === "sources")           sources = event.content;
                                else if (event.type === "delta")        answerRef.current += event.content;
                                else if (event.type === "steps")        setReasoningSteps(event.content || []);
                                else if (event.type === "causal_chain") {
                                    streamCausalChain = event.content;
                                    setCausalChain(event.content);
                                }
                            } catch { }
                        }
                    }
                    streamDone = true;
                } catch {
                    if (attempt >= MAX_RETRIES) throw new Error("网络异常，已达最大重试次数");
                }

                if (streamDone) break;
            }

            clearInterval(intervalId);
            setStreaming(false);
            setStreamingMsgId(null);

            const finalMsgs = newMsgs.map(m =>
                m.id === aiMsgId
                    ? { ...m, content: answerRef.current, sources, causalChain: streamCausalChain ?? undefined }
                    : m
            );
            await updateConversation(convId!, finalMsgs);

        } catch (e) {
            clearInterval(intervalId);
            setLoading(false);
            setStreaming(false);
            setStreamingMsgId(null);
            const errMsg = e instanceof Error ? e.message : "网络异常";
            await updateConversation(convId!, newMsgs.map(m =>
                m.id === aiMsgId ? { ...m, content: errMsg } : m
            ));
        }
    }

    // ── 对话分支 ──────────────────────────────────────────────────────────────
    async function handleBranch(upToIndex: number) {
        if (!activeConv) return;
        const branchedMessages = activeConv.messages.slice(0, upToIndex + 1);
        const branchTitle = `分支: ${branchedMessages[0]?.content?.slice(0, 18) || "新分支"}`;
        const token = localStorage.getItem("token") || "";
        try {
            const res = await fetch("/api/conversations", {
                method:  "POST",
                headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` },
                body:    JSON.stringify({ title: branchTitle, strategy, messages: branchedMessages }),
            });
            const conv = await res.json();
            if (conv?.id) setActiveId(conv.id);
        } catch (e) {
            console.error("分支创建失败:", e);
        }
    }

    async function handleSourceClick(chunkId: string) {
        const stored   = JSON.parse(localStorage.getItem("user") ?? "{}");
        const lastUser = activeConv?.messages.findLast(m => m.role === "user");
        const lastAI   = activeConv?.messages.findLast(m => m.role === "assistant");
        await fetch("/api/feedback", {
            method:  "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                question: lastUser?.content ?? "",
                answer:   lastAI?.content   ?? "",
                sources: [], rating: 1, strategy,
                user_id: stored.user_id ?? "",
                detail: `clicked_source:${chunkId}`,
            }),
        });
    }

    function exportConversation() {
        if (!activeConv || activeConv.messages.length === 0) return;
        const lines = [
            `# ${activeConv.title}`, ``,
            ...activeConv.messages.flatMap(m => [
                m.role === "user" ? `**用户：** ${m.content}` : `**AI：** ${m.content}`,
                ``,
            ]),
            `---`, `*导出时间：${new Date().toLocaleString("zh-CN")}*`,
        ];
        const blob = new Blob([lines.join("\n")], { type: "text/markdown;charset=utf-8" });
        const url  = URL.createObjectURL(blob);
        const a    = document.createElement("a"); a.href = url;
        a.download = `${activeConv.title}_${Date.now()}.md`; a.click();
        URL.revokeObjectURL(url);
    }

    const historyLen = activeConv?.messages.length ?? 0;

    return (
        <div className="flex h-full bg-gray-950">
            {netToast && (
                <NetToast
                    type={netToast.type}
                    label={netToast.label}
                    onClose={() => setNetToast(null)}
                />
            )}
            <ConversationSidebar
                conversations={conversations}
                activeId={activeId}
                onSelect={setActiveId}
                onDelete={deleteConversation}
                onNew={() => createConversation()}
                disableNew={activeConv !== null && activeConv.messages.length === 0}
            />

            <div className="flex-1 flex flex-col min-w-0">
                {/* 顶部栏 */}
                <div className="flex items-center justify-between px-6 py-3 border-b border-gray-800 shrink-0">
                    <div className="text-sm text-gray-400 truncate">
                        {activeConv?.title ?? "选择或新建对话"}
                    </div>
                    <button onClick={exportConversation}
                        disabled={!activeConv || historyLen === 0}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs
                                   text-gray-500 hover:text-gray-300 border border-gray-800
                                   hover:border-gray-600 rounded-lg transition-colors disabled:opacity-30">
                        <Download size={12} /> 导出对话
                    </button>
                </div>

                {/* 消息流 */}
                <div className="flex-1 overflow-auto px-4 py-6">
                    <div className="max-w-3xl mx-auto">
                        {!activeConv || historyLen === 0 ? (
                            <div className="flex flex-col items-center justify-center min-h-64 gap-5 py-10">
                                <div className="text-5xl">✈️</div>
                                <div className="text-gray-500 text-sm">开始提问关于航空工艺规范的问题</div>
                                <div className="flex flex-wrap gap-2 justify-center">
                                    {SUGGESTED.map(q => (
                                        <button key={q} onClick={() => { setInput(q); }}
                                            className="px-3 py-1.5 bg-gray-900 border border-gray-700
                                                       text-xs text-gray-400 rounded-xl
                                                       hover:border-indigo-500 hover:text-white transition-colors">
                                            {q}
                                        </button>
                                    ))}
                                </div>
                                {/* 反事实示例 */}
                                <div className="w-full max-w-md">
                                    <div className="flex items-center gap-2 mb-2">
                                        <span className="text-xs text-amber-600 font-medium">反事实假设推理示例</span>
                                        <span className="text-xs text-gray-600">— 选择"反事实"策略后尝试</span>
                                    </div>
                                    <div className="flex flex-col gap-1.5">
                                        {COUNTERFACTUAL_EXAMPLES.map(q => (
                                            <button key={q}
                                                onClick={() => { setInput(q); setStrategy("counterfactual"); }}
                                                className="px-3 py-2 bg-amber-950/20 border border-amber-800/30
                                                           text-xs text-amber-400/80 rounded-xl text-left
                                                           hover:border-amber-600/50 hover:text-amber-300 transition-colors">
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
                                        {/* 反事实因果链面板：显示在触发它的 assistant 消息上方 */}
                                        {msg.role === "assistant" && (
                                            msg.causalChain
                                                ? <CausalChainPanel data={msg.causalChain} />
                                                : streaming && msg.id === streamingMsgId && causalChain
                                                    ? <CausalChainPanel data={causalChain} />
                                                    : null
                                        )}
                                        <MessageBubble
                                            role={msg.role}
                                            content={msg.content}
                                            sources={msg.sources}
                                            images={msg.images}
                                            streaming={streaming && msg.id === streamingMsgId}
                                            onSourceClick={handleSourceClick}
                                            onBranch={msg.role === "assistant" && !streaming
                                                ? () => handleBranch(i)
                                                : undefined}
                                        />
                                    </div>
                                ))}
                            </>
                        )}
                        {loading && <SkeletonCard />}
                        <div ref={bottomRef} />
                    </div>
                </div>

                {/* 输入框 */}
                <ConversationInput
                    value={input}
                    strategy={strategy}
                    loading={loading}
                    streaming={streaming}
                    historyLen={historyLen}
                    pendingImages={pendingImages}
                    onChange={setInput}
                    onStrategy={setStrategy}
                    onSubmit={handleSubmit}
                    onClear={clearConversation}
                    onAddImages={imgs => setPendingImages(prev => [...prev, ...imgs])}
                    onRemoveImage={idx => setPendingImages(prev => prev.filter((_, i) => i !== idx))}
                />
            </div>
        </div>
    );
}
