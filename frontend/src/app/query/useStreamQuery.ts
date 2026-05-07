"use client";

import { useRef, useState } from "react";
import type { NetToastType } from "@/components/NetToast";
import { getApiBaseUrl, getAuthHeaders } from "@/lib/api";
import type { ReasoningStep } from "./ReasoningChain";
import type {
  CausalChainData,
  ClarificationInfo,
  LLMErrorInfo,
  Message,
  QueryMetrics,
  SourceSection,
  Strategy,
} from "./types";

interface UseStreamQueryParams {
  strategy: Strategy;
  useHyde: boolean;
  hydeAlpha: number;
  activeId: string | null;
  activeConv: { id: string; messages: Message[] } | null;
  conversations: { id: string; messages: Message[] }[];
  createConversation: (title?: string, strategy?: Strategy) => Promise<string>;
  updateConversation: (
    id: string,
    messages: Message[],
    title?: string,
  ) => Promise<void>;
  showNetToast: (
    type: NetToastType,
    label: string,
    autoDismissMs?: number,
  ) => void;
}

function normalizeAnswerText(text: string) {
  return text.replace(/\u00A0/g, " ").replace(/[ \t]{3,}/g, " ");
}

function isAbortError(error: unknown) {
  return (
    (error instanceof DOMException && error.name === "AbortError") ||
    (error instanceof Error && error.name === "AbortError")
  );
}

export function useStreamQuery({
  strategy,
  useHyde,
  hydeAlpha,
  activeId,
  activeConv: _activeConv,
  conversations,
  createConversation,
  updateConversation,
  showNetToast,
}: UseStreamQueryParams) {
  const API = getApiBaseUrl();
  const [loading, setLoading] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [streamingMsgId, setStreamingMsgId] = useState<string | null>(null);
  const [streamingText, setStreamingText] = useState("");
  const [reasoningSteps, setReasoningSteps] = useState<ReasoningStep[]>([]);
  const [causalChain, setCausalChain] = useState<CausalChainData | null>(null);
  const [streamingConvId, setStreamingConvId] = useState<string | null>(null);
  const answerRef = useRef("");
  const abortRef = useRef<AbortController | null>(null);
  const requestSeqRef = useRef(0);

  async function submit(
    question: string,
    images: string[],
    options?: { replaceFromIndex?: number },
  ) {
    const requestSeq = ++requestSeqRef.current;
    let convId = activeId;
    if (!convId) {
      convId = await createConversation(question.slice(0, 20), strategy);
    }
    if (!convId) return;

    const conv = conversations.find((c) => c.id === convId);
    const prevMsgs =
      options?.replaceFromIndex !== undefined
        ? (conv?.messages ?? []).slice(0, options.replaceFromIndex)
        : (conv?.messages ?? []);

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

    setStreamingConvId(convId);
    setStreamingMsgId(aiMsgId);
    setLoading(true);
    setReasoningSteps([]);
    setCausalChain(null);
    setStreamingText("");
    answerRef.current = "";
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    const history = prevMsgs.map((m) => ({
      role: m.role,
      content: m.content,
    }));

    // 每 800ms 同步一次流式内容到对话状态，供侧边栏实时预览；
    // 流结束后会再做一次完整写入，此处仅用于 UI 视觉反馈。
    const intervalId = setInterval(() => {
      if (!convId) return;
      updateConversation(
        convId,
        newMsgs.map((m) =>
          m.id === aiMsgId
            ? { ...m, content: normalizeAnswerText(answerRef.current) }
            : m,
        ),
      );
    }, 800);

    let sources: SourceSection[] = [];
    let streamCausalChain: CausalChainData | null = null;
    let streamFollowUps: string[] = [];
    let streamError: LLMErrorInfo | null = null;
    let streamExpansionInfo: string[] = [];
    let streamMetrics: QueryMetrics | null = null;
    let streamClarification: ClarificationInfo | null = null;

    const MAX_RETRIES = 3;
    let retryDelay = 1000;

    try {
      for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
        if (attempt > 0) {
          showNetToast(
            "reconnecting",
            `连接中断，${retryDelay / 1000}s 后重试 (${attempt}/${MAX_RETRIES})…`,
          );
          await new Promise((r) => setTimeout(r, retryDelay));
          retryDelay = Math.min(retryDelay * 2, 8000);
          answerRef.current = "";
          setStreamingText("");
          showNetToast("reconnecting", "正在重连…");
        }

        let streamDone = false;
        try {
          sources = [];
          streamCausalChain = null;
          streamFollowUps = [];
          streamError = null;
          streamExpansionInfo = [];
          const headers = await getAuthHeaders({
            "Content-Type": "application/json",
          });
          const res = await fetch(`${API}/api/query/stream`, {
            method: "POST",
            headers,
            signal: controller.signal,
            body: JSON.stringify({
              question,
              strategy,
              history,
              images,
              use_hyde: useHyde,
              hyde_alpha: hydeAlpha,
            }),
          });
          if (!res.ok) throw new Error("请求失败");

          if (attempt === 0) {
            setLoading(false);
            setStreaming(true);
          } else {
            showNetToast("online", "已重连", 3000);
          }

          const reader = res.body?.getReader();
          if (!reader) throw new Error("流式响应为空");
          const decoder = new TextDecoder();
          let buffer = "";

          while (true) {
            if (controller.signal.aborted) {
              throw new DOMException("Aborted", "AbortError");
            }
            const { done, value } = await reader.read();
            if (done) {
              buffer += decoder.decode();
              if (buffer.trim()) {
                const lines = buffer.split("\n");
                buffer = "";
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
                    } else if (event.type === "delta") {
                      answerRef.current = normalizeAnswerText(
                        answerRef.current + event.content,
                      );
                      setStreamingText(answerRef.current);
                    } else if (event.type === "steps") {
                      setReasoningSteps((prev) => [...prev, ...event.content]);
                    } else if (event.type === "status") {
                      showNetToast("online", event.content, 2000);
                    } else if (event.type === "causal_chain") {
                      streamCausalChain = event.content;
                      setCausalChain(event.content);
                    } else if (event.type === "follow_up") {
                      streamFollowUps = event.content || [];
                    } else if (event.type === "expansion") {
                      streamExpansionInfo = event.content || [];
                    } else if (event.type === "metrics") {
                      streamMetrics = event.content;
                    } else if (event.type === "error") {
                      streamError = {
                        code: event.code ?? "unknown_error",
                        message:
                          event.message ?? event.content ?? "AI 服务异常",
                        status_code: event.status_code ?? null,
                        endpoint: event.endpoint ?? "",
                      };
                    }
                  } catch {}
                }
              }
              break;
            }

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n");
            buffer = lines.pop() || "";

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
                } else if (event.type === "clarification_needed") {
                  streamClarification = {
                    message:
                      event.message ??
                      "您的问题有些宽泛，请选择您想了解的方向：",
                    options: event.options || [],
                    originalQuestion: event.original_question ?? question,
                  };
                  answerRef.current = streamClarification.message;
                } else if (event.type === "delta") {
                  answerRef.current = normalizeAnswerText(
                    answerRef.current + event.content,
                  );
                  setStreamingText(answerRef.current);
                } else if (event.type === "steps") {
                  setReasoningSteps((prev) => [...prev, ...event.content]);
                } else if (event.type === "status") {
                  showNetToast("online", event.content, 2000);
                } else if (event.type === "causal_chain") {
                  streamCausalChain = event.content;
                  setCausalChain(event.content);
                } else if (event.type === "follow_up") {
                  streamFollowUps = event.content || [];
                } else if (event.type === "expansion") {
                  streamExpansionInfo = event.content || [];
                } else if (event.type === "metrics") {
                  streamMetrics = event.content;
                } else if (event.type === "error") {
                  streamError = {
                    code: event.code ?? "unknown_error",
                    message: event.message ?? event.content ?? "AI 服务异常",
                    status_code: event.status_code ?? null,
                    endpoint: event.endpoint ?? "",
                  };
                }
              } catch {}
            }
          }
          if (!streamDone) throw new Error("流式响应异常结束");
        } catch (error) {
          if (controller.signal.aborted || isAbortError(error)) {
            streamDone = true;
            break;
          }
          if (attempt >= MAX_RETRIES) {
            throw new Error("网络异常，已达最大重试次数");
          }
        }
        if (streamDone) break;
      }

      clearInterval(intervalId);
      const persistedAnswer = normalizeAnswerText(answerRef.current);
      const finalMsgs = newMsgs.map((m) =>
        m.id === aiMsgId
          ? {
              ...m,
              content: streamClarification?.message ?? persistedAnswer,
              sources,
              clarification: streamClarification ?? undefined,
              causalChain: streamCausalChain ?? undefined,
              followUpQuestions:
                streamFollowUps.length > 0 ? streamFollowUps : undefined,
              errorInfo: streamError ?? undefined,
              expansionInfo:
                streamExpansionInfo.length > 0
                  ? streamExpansionInfo
                  : undefined,
              metrics: streamMetrics ?? undefined,
            }
          : m,
      );
      await updateConversation(
        convId,
        persistedAnswer.trim() ? finalMsgs : newMsgs.slice(0, -1),
      );
      if (requestSeq === requestSeqRef.current) {
        setStreaming(false);
        setStreamingMsgId(null);
        setStreamingConvId(null);
        abortRef.current = null;
      }
    } catch (e) {
      clearInterval(intervalId);
      if (isAbortError(e)) {
        const persistedAnswer = normalizeAnswerText(answerRef.current);
        await updateConversation(
          convId,
          persistedAnswer.trim()
            ? newMsgs.map((m) =>
                m.id === aiMsgId
                  ? {
                      ...m,
                      content: streamClarification?.message ?? persistedAnswer,
                      sources,
                      clarification: streamClarification ?? undefined,
                      causalChain: streamCausalChain ?? undefined,
                      followUpQuestions:
                        streamFollowUps.length > 0
                          ? streamFollowUps
                          : undefined,
                      errorInfo: streamError ?? undefined,
                      expansionInfo:
                        streamExpansionInfo.length > 0
                          ? streamExpansionInfo
                          : undefined,
                      metrics: streamMetrics ?? undefined,
                    }
                  : m,
              )
            : newMsgs.slice(0, -1),
        );
        if (requestSeq === requestSeqRef.current) {
          setLoading(false);
          setStreaming(false);
          setStreamingMsgId(null);
          setStreamingConvId(null);
          abortRef.current = null;
        }
        return;
      }
      const errMsg = e instanceof Error ? e.message : "网络异常";
      await updateConversation(
        convId,
        newMsgs.map((m) => (m.id === aiMsgId ? { ...m, content: errMsg } : m)),
      );
      if (requestSeq === requestSeqRef.current) {
        setLoading(false);
        setStreaming(false);
        setStreamingMsgId(null);
        setStreamingConvId(null);
        abortRef.current = null;
      }
    }
  }

  return {
    loading,
    streaming,
    streamingMsgId,
    streamingText,
    streamingConvId,
    reasoningSteps,
    causalChain,
    submit,
    cancel: () => abortRef.current?.abort(),
    setReasoningSteps,
    setCausalChain,
  };
}
