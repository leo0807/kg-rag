"use client";

import { useRef, useState } from "react";
import type { NetToastType } from "@/components/NetToast";
import { Message, SourceSection, Strategy, CausalChainData, LLMErrorInfo } from "./types";
import { ReasoningStep } from "./ReasoningChain";

interface UseStreamQueryParams {
    strategy:           Strategy;
    activeId:           string | null;
    activeConv:         { id: string; messages: Message[] } | null;
    conversations:      { id: string; messages: Message[] }[];
    createConversation: (title?: string, strategy?: Strategy) => Promise<string>;
    updateConversation: (id: string, messages: Message[], title?: string) => Promise<void>;
    showNetToast:       (type: NetToastType, label: string, autoDismissMs?: number) => void;
}

export function useStreamQuery({
    strategy, activeId, activeConv, conversations,
    createConversation, updateConversation, showNetToast,
}: UseStreamQueryParams) {
    const [loading,        setLoading]        = useState(false);
    const [streaming,      setStreaming]       = useState(false);
    const [streamingMsgId, setStreamingMsgId] = useState<string | null>(null);
    const [reasoningSteps, setReasoningSteps] = useState<ReasoningStep[]>([]);
    const [causalChain,    setCausalChain]    = useState<CausalChainData | null>(null);
    const answerRef = useRef("");

    async function submit(
        question: string,
        images: string[],
    ) {
        let convId = activeId;
        if (!convId) {
            convId = await createConversation(question.slice(0, 20), strategy);
        }

        const conv     = conversations.find(c => c.id === convId);
        const prevMsgs = conv?.messages ?? [];

        const userMsg: Message = {
            id: `user_${Date.now()}`, role: "user", content: question,
            images: images.length > 0 ? images : undefined, timestamp: Date.now(),
        };
        const aiMsgId = `ai_${Date.now()}`;
        const aiMsg: Message = { id: aiMsgId, role: "assistant", content: "", sources: [], timestamp: Date.now() };

        const newMsgs  = [...prevMsgs, userMsg, aiMsg];
        const newTitle = prevMsgs.length === 0 ? question.slice(0, 20) : undefined;
        await updateConversation(convId, newMsgs, newTitle);

        setStreamingMsgId(aiMsgId);
        setLoading(true);
        setReasoningSteps([]);
        setCausalChain(null);
        answerRef.current = "";

        const history = (activeConv?.messages ?? []).map(m => ({ role: m.role, content: m.content }));

        const intervalId = setInterval(() => {
            updateConversation(convId!, newMsgs.map(m =>
                m.id === aiMsgId ? { ...m, content: answerRef.current } : m
            ));
        }, 150);

        let sources: SourceSection[] = [];
        let streamCausalChain: CausalChainData | null = null;
        let streamFollowUps: string[] = [];
        let streamError: LLMErrorInfo | null = null;

        const MAX_RETRIES = 3;
        let retryDelay    = 1000;

        try {
            for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
                if (attempt > 0) {
                    showNetToast("reconnecting", `连接中断，${retryDelay / 1000}s 后重试 (${attempt}/${MAX_RETRIES})…`);
                    await new Promise(r => setTimeout(r, retryDelay));
                    retryDelay = Math.min(retryDelay * 2, 8000);
                    answerRef.current = "";
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

                    if (attempt === 0) { setLoading(false); setStreaming(true); }
                    else { showNetToast("online", "已重连", 3000); }

                    const reader  = res.body!.getReader();
                    const decoder = new TextDecoder();
                    let buffer = ""; // 新增缓冲区处理断裂的字符

                    while (true) {
                        const { done, value } = await reader.read();
                        if (done) break;
                        
                        buffer += decoder.decode(value, { stream: true });
                        const lines = buffer.split("\n");
                        buffer = lines.pop() || ""; // 最后一项可能不完整，留入缓冲区

                        for (const line of lines) {
                            if (!line.startsWith("data: ")) continue;
                            const data = line.slice(6);
                            if (data === "[DONE]") {
                                streamDone = true;
                                break;
                            }
                            try {
                                const event = JSON.parse(data);
                                if (event.type === "sources") {
                                    sources = [...sources, ...event.content];
                                }
                                else if (event.type === "delta")        answerRef.current += event.content;
                                else if (event.type === "steps")        setReasoningSteps(prev => [...prev, ...event.content]);
                                else if (event.type === "status")       showNetToast("online", event.content, 2000);
                                else if (event.type === "causal_chain") { streamCausalChain = event.content; setCausalChain(event.content); }
                                else if (event.type === "follow_up")    streamFollowUps = event.content || [];
                                else if (event.type === "error")        streamError = {
                                    code:        event.code        ?? "unknown_error",
                                    message:     event.message     ?? event.content ?? "AI 服务异常",
                                    status_code: event.status_code ?? null,
                                    endpoint:    event.endpoint    ?? "",
                                };
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
                m.id === aiMsgId ? {
                    ...m,
                    content:           answerRef.current,
                    sources,
                    causalChain:       streamCausalChain ?? undefined,
                    followUpQuestions: streamFollowUps.length > 0 ? streamFollowUps : undefined,
                    errorInfo:         streamError ?? undefined,
                } : m
            );
            await updateConversation(convId!, finalMsgs);

        } catch (e) {
            clearInterval(intervalId);
            setLoading(false); setStreaming(false); setStreamingMsgId(null);
            const errMsg = e instanceof Error ? e.message : "网络异常";
            await updateConversation(convId!, newMsgs.map(m => m.id === aiMsgId ? { ...m, content: errMsg } : m));
        }
    }

    return { loading, streaming, streamingMsgId, reasoningSteps, causalChain, submit, setReasoningSteps, setCausalChain };
}
