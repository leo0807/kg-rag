"use client";

import { useState, useRef, useEffect } from "react";
import { Download } from "lucide-react";
import SkeletonCard from "@/components/SkeletonCard";
import ConversationSidebar from "./ConversationSidebar";
import MessageBubble from "./MessageBubble";
import ConversationInput from "./ConversationInput";
import { useConversations } from "./useConversations";
import { Message, SourceSection, Strategy } from "./types";

const SUGGESTED = [
    "液压导管修理需要什么工具",
    "CPS1220 的技术要求是什么",
    "收压接头的安装步骤有哪些",
];

export default function QueryPage() {
    const {
        conversations, activeId, activeConv,
        setActiveId, createConversation,
        updateConversation, deleteConversation, clearConversation,
    } = useConversations();

    const [input, setInput] = useState("");
    const [strategy, setStrategy] = useState<Strategy>("parallel");
    const [loading, setLoading] = useState(false);
    const [streaming, setStreaming] = useState(false);
    const [streamingMsgId, setStreamingMsgId] = useState<string | null>(null);
    const [pendingImages, setPendingImages] = useState<string[]>([]);
    const answerRef = useRef("");
    const bottomRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [activeConv?.messages.length, streaming]);

    async function handleSubmit() {
        if ((!input.trim() && pendingImages.length === 0) || loading || streaming) return;

        const question = input.trim();
        const images = [...pendingImages];
        setInput("");
        setPendingImages([]);

        // 确保有活跃会话
        let convId = activeId;
        if (!convId) {
            convId = await createConversation(question.slice(0, 20), strategy);
        }

        const conv = conversations.find(c => c.id === convId);
        const prevMsgs = conv?.messages ?? [];

        const userMsg: Message = {
            id: `user_${Date.now()}`,
            role: "user",
            content: question,
            images: images.length > 0 ? images : undefined,
            timestamp: Date.now(),
        };

        const aiMsgId = `ai_${Date.now()}`;
        const aiMsg: Message = {
            id: aiMsgId,
            role: "assistant",
            content: "",
            sources: [],
            timestamp: Date.now(),
        };

        const newMsgs = [...prevMsgs, userMsg, aiMsg];
        const newTitle = prevMsgs.length === 0 ? question.slice(0, 20) : undefined;
        await updateConversation(convId, newMsgs, newTitle);

        setStreamingMsgId(aiMsgId);
        setLoading(true);
        answerRef.current = "";

        // 构建历史（不含当前问题）
        const history = (activeConv?.messages ?? []).map(m => ({
            role: m.role,
            content: m.content,
        }));
        try {
            const token = localStorage.getItem("token") ?? "";
            const res = await fetch("http://localhost:8000/api/query/stream", {
                method: "POST",
                headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` },
                body: JSON.stringify({ question, strategy, history, images }),
            });

            if (!res.ok) throw new Error("请求失败");
            setLoading(false);
            setStreaming(true);

            const reader = res.body!.getReader();
            const decoder = new TextDecoder();
            let sources: SourceSection[] = [];

            // 定时刷新流式内容
            const intervalId = setInterval(() => {
                updateConversation(convId!, newMsgs.map(m =>
                    m.id === aiMsgId ? { ...m, content: answerRef.current } : m
                ));
            }, 150);

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                for (const line of decoder.decode(value).split("\n")) {
                    if (!line.startsWith("data: ")) continue;
                    const data = line.slice(6);
                    if (data === "[DONE]") break;
                    try {
                        const event = JSON.parse(data);
                        if (event.type === "sources") sources = event.content;
                        else if (event.type === "delta") answerRef.current += event.content;
                    } catch { }
                }
            }

            clearInterval(intervalId);
            setStreaming(false);
            setStreamingMsgId(null);

            // 最终写入完整答案和来源
            const finalMsgs = newMsgs.map(m =>
                m.id === aiMsgId
                    ? { ...m, content: answerRef.current, sources }
                    : m
            );
            await updateConversation(convId!, finalMsgs);

        } catch (e) {
            setLoading(false);
            setStreaming(false);
            setStreamingMsgId(null);
            const errMsg = e instanceof Error ? e.message : "网络异常";
            await updateConversation(convId!, newMsgs.map(m =>
                m.id === aiMsgId ? { ...m, content: errMsg } : m
            ));
        }
    }

    async function handleSourceClick(chunkId: string) {
        const stored = JSON.parse(localStorage.getItem("user") ?? "{}");
        const lastUser = activeConv?.messages.findLast(m => m.role === "user");
        const lastAI = activeConv?.messages.findLast(m => m.role === "assistant");
        await fetch("/api/feedback", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                question: lastUser?.content ?? "",
                answer: lastAI?.content ?? "",
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
                m.role === "user"
                    ? `**用户：** ${m.content}`
                    : `**AI：** ${m.content}`,
                ``,
            ]),
            `---`, `*导出时间：${new Date().toLocaleString("zh-CN")}*`,
        ];
        const blob = new Blob([lines.join("\n")], { type: "text/markdown;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a"); a.href = url;
        a.download = `${activeConv.title}_${Date.now()}.md`; a.click();
        URL.revokeObjectURL(url);
    }

    const historyLen = activeConv?.messages.length ?? 0;

    return (
        <div className="flex h-full bg-gray-950">
            <ConversationSidebar
                conversations={conversations}
                activeId={activeId}
                onSelect={setActiveId}
                onDelete={deleteConversation}
                onNew={() => createConversation()}
            />

            <div className="flex-1 flex flex-col min-w-0">
                {/* 顶部栏 */}
                <div className="flex items-center justify-between px-6 py-3
                        border-b border-gray-800 shrink-0">
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
                            <div className="flex flex-col items-center justify-center h-64 gap-4">
                                <div className="text-5xl">✈️</div>
                                <div className="text-gray-500 text-sm">开始提问关于航空工艺规范的问题</div>
                                <div className="flex flex-wrap gap-2 justify-center">
                                    {SUGGESTED.map(q => (
                                        <button key={q} onClick={() => setInput(q)}
                                            className="px-3 py-1.5 bg-gray-900 border border-gray-700
                                 text-xs text-gray-400 rounded-xl
                                 hover:border-indigo-500 hover:text-white transition-colors">
                                            {q}
                                        </button>
                                    ))}
                                </div>
                            </div>
                        ) : (
                            activeConv.messages.map(msg => (
                                <MessageBubble
                                    key={msg.id}
                                    role={msg.role}
                                    content={msg.content}
                                    sources={msg.sources}
                                    images={msg.images}
                                    streaming={streaming && msg.id === streamingMsgId}
                                    onSourceClick={handleSourceClick}
                                />
                            ))
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