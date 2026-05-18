"use client";

import { useRef, useState } from "react";
import type { NetToastType } from "@/components/NetToast";
import { getApiBaseUrl, getAuthHeaders } from "@/lib/api";
import type { StreamPhase } from "./ProgressIndicator";
import type { ReasoningStep } from "./ReasoningChain";
import type {
  AgentStepInfo,
  AnswerImage,
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

function upsertAgentStep(
  steps: AgentStepInfo[],
  nextStep: AgentStepInfo,
): AgentStepInfo[] {
  const index = steps.findIndex((step) => step.step === nextStep.step);
  if (index === -1) return [...steps, nextStep];
  const copy = [...steps];
  copy[index] = { ...copy[index], ...nextStep };
  return copy;
}

function isAbortError(error: unknown) {
  return (
    (error instanceof DOMException && error.name === "AbortError") ||
    (error instanceof Error && error.name === "AbortError")
  );
}

type StreamErrorKind =
  | "network"
  | "auth"
  | "business"
  | "stream_truncated"
  | "stream_empty"
  | "interrupted";

interface StreamErrorInfo extends LLMErrorInfo {
  kind: StreamErrorKind;
  retryable: boolean;
  httpStatus: number | null;
}

type StreamEvent = {
  type: string;
  content?: unknown;
  message?: string;
  options?: string[];
  original_question?: string;
  step?: number | string;
  action?: string;
  status?: string;
  input?: unknown;
  result_summary?: string;
  code?: string;
  status_code?: number | null;
  httpStatus?: number | null;
  error?: { code?: string; message?: string };
};

class StreamTerminalError extends Error {
  constructor(public error: StreamErrorInfo) {
    super(error.message);
    this.name = "StreamTerminalError";
  }
}

function extractErrorMessage(body: unknown, fallback: string): string {
  if (typeof body === "string") return body.trim() || fallback;
  if (!body || typeof body !== "object") return fallback;
  const obj = body as {
    detail?: string | { msg?: string }[];
    message?: string;
    error?: { message?: string; code?: string };
  };
  if (typeof obj.message === "string" && obj.message.trim()) return obj.message;
  if (typeof obj.detail === "string" && obj.detail.trim()) return obj.detail;
  if (Array.isArray(obj.detail)) {
    const detailMsg = obj.detail
      .map((item) => item?.msg)
      .filter((msg): msg is string => typeof msg === "string" && msg.trim())
      .join("; ");
    if (detailMsg) return detailMsg;
  }
  if (
    obj.error &&
    typeof obj.error.message === "string" &&
    obj.error.message.trim()
  ) {
    return obj.error.message;
  }
  return fallback;
}

function classifyHttpError(status: number, body: unknown): StreamErrorInfo {
  const base = {
    status_code: status,
    endpoint: "",
  };

  if (status === 401) {
    return {
      ...base,
      kind: "auth",
      code: "unknown_error",
      message: extractErrorMessage(body, "登录已过期，请重新登录"),
      retryable: false,
      httpStatus: 401,
    };
  }

  if (status === 403) {
    const code =
      body && typeof body === "object"
        ? ((body as { code?: string; error?: { code?: string } }).code ??
          (body as { error?: { code?: string } }).error?.code)
        : undefined;
    if (code === "quota_exceeded") {
      return {
        ...base,
        kind: "business",
        code,
        message: extractErrorMessage(body, "AI 服务额度不足，请联系管理员充值"),
        retryable: false,
        httpStatus: 403,
      };
    }
    return {
      ...base,
      kind: "auth",
      code: "unknown_error",
      message: extractErrorMessage(body, "无权访问该资源"),
      retryable: false,
      httpStatus: 403,
    };
  }

  if (status >= 400 && status < 500) {
    const code =
      body && typeof body === "object"
        ? ((body as { code?: string; error?: { code?: string } }).code ??
          (body as { error?: { code?: string } }).error?.code)
        : undefined;
    return {
      ...base,
      kind: "business",
      code: code ?? "unknown_error",
      message: extractErrorMessage(body, `请求错误 (${status})`),
      retryable: false,
      httpStatus: status,
    };
  }

  if (status >= 500) {
    return {
      ...base,
      kind: "business",
      code: "service_unavailable",
      message: extractErrorMessage(body, "服务暂时异常，请稍后重试"),
      retryable: false,
      httpStatus: status,
    };
  }

  return {
    ...base,
    kind: "business",
    code: "unknown_error",
    message: `未知错误 (${status})`,
    retryable: false,
    httpStatus: status,
  };
}

function classifyFetchException(err: unknown): StreamErrorInfo {
  if (err instanceof DOMException && err.name === "AbortError") {
    return {
      kind: "interrupted",
      code: "unknown_error",
      message: "请求已取消",
      status_code: null,
      endpoint: "",
      retryable: false,
      httpStatus: null,
    };
  }
  if (err instanceof TypeError) {
    return {
      kind: "network",
      code: "network_error",
      message: "网络连接失败，请检查网络后重试",
      status_code: null,
      endpoint: "",
      retryable: true,
      httpStatus: null,
    };
  }
  return {
    kind: "network",
    code: "network_error",
    message: err instanceof Error ? err.message : "未知网络错误",
    status_code: null,
    endpoint: "",
    retryable: true,
    httpStatus: null,
  };
}

function classifySseError(event: {
  code?: string;
  status_code?: number | null;
  httpStatus?: number | null;
  message?: string;
  content?: string;
  error?: { code?: string; message?: string };
}): StreamErrorInfo {
  const code = event.code ?? event.error?.code;
  const status = event.status_code ?? event.httpStatus ?? null;
  const message =
    event.message ?? event.error?.message ?? event.content ?? "处理失败";

  if (code === "quota_exceeded") {
    return {
      kind: "business",
      code,
      message: "AI 服务额度不足，请联系管理员充值",
      status_code: status,
      endpoint: "",
      retryable: false,
      httpStatus: status,
    };
  }

  if (status === 401 || status === 403) {
    return {
      kind: "auth",
      code: "unknown_error",
      message,
      status_code: status,
      endpoint: "",
      retryable: false,
      httpStatus: status,
    };
  }

  return {
    kind: "business",
    code: code ?? "unknown_error",
    message,
    status_code: status,
    endpoint: "",
    retryable: false,
    httpStatus: status,
  };
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
  const [streamPhase, setStreamPhase] = useState<StreamPhase>("idle");
  const [retrievedCount, setRetrievedCount] = useState<number | null>(null);
  const [, setStreamAnswerImages] = useState<AnswerImage[]>([]);
  const [reasoningSteps, setReasoningSteps] = useState<ReasoningStep[]>([]);
  const [causalChain, setCausalChain] = useState<CausalChainData | null>(null);
  const [streamingConvId, setStreamingConvId] = useState<string | null>(null);
  const answerRef = useRef("");
  const abortRef = useRef<AbortController | null>(null);
  const requestSeqRef = useRef(0);

  async function submit(
    question: string,
    images: string[],
    options?: {
      replaceFromIndex?: number;
      skipClarification?: boolean;
      docHints?: string[];
    },
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
    setStreamPhase("searching");
    setRetrievedCount(null);
    setStreamAnswerImages([]);
    answerRef.current = "";
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    let requestTimedOut = false;
    let requestTimeoutId: ReturnType<typeof setTimeout> | null = null;
    const clearRequestTimeout = () => {
      if (requestTimeoutId) {
        clearTimeout(requestTimeoutId);
        requestTimeoutId = null;
      }
    };

    const history = prevMsgs.map((m) => ({
      role: m.role,
      content: m.content,
    }));

    // 每 800ms 同步一次流式内容到对话状态，供侧边栏实时预览；
    // 流结束后会再做一次完整写入，此处仅用于 UI 视觉反馈。
    const intervalId = setInterval(() => {
      syncAssistantMessage(answerRef.current);
    }, 800);

    let sources: SourceSection[] = [];
    let streamCausalChain: CausalChainData | null = null;
    let streamFollowUps: string[] = [];
    let streamError: StreamErrorInfo | null = null;
    let streamExpansionInfo: string[] = [];
    let streamMetrics: QueryMetrics | null = null;
    let streamClarification: ClarificationInfo | null = null;
    let streamAgentSteps: AgentStepInfo[] = [];
    let currentAnswerImages: AnswerImage[] = [];

    const handleStreamEvent = (event: StreamEvent) => {
      if (event.type === "sources") {
        sources = [...sources, ...event.content];
        setRetrievedCount(sources.length);
        return;
      }
      if (event.type === "sources_update") {
        sources = Array.isArray(event.content) ? event.content : sources;
        setRetrievedCount(sources.length);
        return;
      }
      if (event.type === "clarification_needed") {
        streamClarification = {
          message: event.message ?? "您的问题有些宽泛，请选择您想了解的方向：",
          options: event.options || [],
          originalQuestion: event.original_question ?? question,
        };
        answerRef.current = streamClarification.message;
        return;
      }
      if (event.type === "delta") {
        receivedAnyDelta.current = true;
        setStreamPhase("generating");
        answerRef.current = normalizeAnswerText(
          answerRef.current + event.content,
        );
        setStreamingText(answerRef.current);
        return;
      }
      if (event.type === "steps") {
        setReasoningSteps((prev) => [...prev, ...event.content]);
        return;
      }
      if (event.type === "images") {
        currentAnswerImages = Array.isArray(event.content) ? event.content : [];
        setStreamAnswerImages(currentAnswerImages);
        syncAssistantMessage(answerRef.current);
        return;
      }
      if (event.type === "agent_step") {
        streamAgentSteps = upsertAgentStep(streamAgentSteps, {
          step: Number(event.step ?? 0),
          action: String(event.action ?? ""),
          status:
            event.status === "failed"
              ? "failed"
              : event.status === "done"
                ? "done"
                : "running",
          input: event.input,
          result_summary: event.result_summary,
        });
        syncAssistantMessage(answerRef.current);
        return;
      }
      if (event.type === "agent_steps") {
        streamAgentSteps = Array.isArray(event.content)
          ? event.content
          : streamAgentSteps;
        syncAssistantMessage(answerRef.current);
        return;
      }
      if (event.type === "status") {
        showNetToast("online", event.content, 2000);
        if (String(event.content).includes("检索")) {
          setStreamPhase("searching");
        } else if (String(event.content).includes("生成")) {
          setStreamPhase("generating");
        }
        return;
      }
      if (event.type === "causal_chain") {
        streamCausalChain = event.content;
        setCausalChain(event.content);
        return;
      }
      if (event.type === "follow_up") {
        streamFollowUps = event.content || [];
        return;
      }
      if (event.type === "expansion") {
        streamExpansionInfo = event.content || [];
        return;
      }
      if (event.type === "metrics") {
        streamMetrics = event.content;
        return;
      }
      if (event.type === "error") {
        const classified = classifySseError(event);
        streamError = classified;
        if (classified.kind === "auth" && classified.httpStatus === 401) {
          applyAuthRedirect();
        }
        throw new StreamTerminalError(classified);
      }
    };

    const syncAssistantMessage = (content: string) => {
      if (!convId) return;
      void updateConversation(
        convId,
        newMsgs.map((m) =>
          m.id === aiMsgId
            ? {
                ...m,
                content:
                  streamClarification?.message ?? normalizeAnswerText(content),
                sources,
                clarification: streamClarification ?? undefined,
                agentSteps:
                  streamAgentSteps.length > 0 ? streamAgentSteps : undefined,
                answerImages:
                  currentAnswerImages.length > 0
                    ? currentAnswerImages
                    : undefined,
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
        ),
      );
    };

    const MAX_RETRIES = 2;
    let retryDelay = 1000;

    const applyAuthRedirect = () => {
      if (typeof window === "undefined") return;
      localStorage.removeItem("token");
      localStorage.removeItem("user");
      window.location.href = "/login";
    };

    const parseResponseBody = async (res: Response) => {
      const text = await res.text();
      if (!text.trim()) return null;
      try {
        return JSON.parse(text);
      } catch {
        return { detail: text };
      }
    };

    const persistCurrentAnswer = async (contentOverride?: string) => {
      if (!convId) return;
      const persistedAnswer = normalizeAnswerText(answerRef.current);
      const finalContent =
        contentOverride ?? streamClarification?.message ?? persistedAnswer;
      const displayContent = finalContent || streamError?.message || "";
      const shouldKeepAssistant =
        Boolean(displayContent.trim()) ||
        Boolean(streamError) ||
        Boolean(streamClarification) ||
        sources.length > 0 ||
        streamAgentSteps.length > 0 ||
        currentAnswerImages.length > 0 ||
        Boolean(streamCausalChain) ||
        streamFollowUps.length > 0 ||
        streamExpansionInfo.length > 0 ||
        Boolean(streamMetrics);

      const finalMsgs = newMsgs.map((m) =>
        m.id === aiMsgId
          ? {
              ...m,
              content: displayContent,
              sources,
              clarification: streamClarification ?? undefined,
              agentSteps:
                streamAgentSteps.length > 0 ? streamAgentSteps : undefined,
              answerImages:
                currentAnswerImages.length > 0
                  ? currentAnswerImages
                  : undefined,
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
        shouldKeepAssistant ? finalMsgs : newMsgs.slice(0, -1),
      );
    };

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
          streamAgentSteps = [];
          currentAnswerImages = [];
          setRetrievedCount(null);
          setStreamAnswerImages([]);
          showNetToast("reconnecting", "正在重连…");
        }

        let streamDone = false;
        const receivedAnyDelta = { current: false };
        try {
          requestTimedOut = false;
          requestTimeoutId = setTimeout(() => {
            requestTimedOut = true;
            controller.abort();
          }, 120000);
          sources = [];
          streamCausalChain = null;
          streamFollowUps = [];
          streamError = null;
          streamExpansionInfo = [];
          currentAnswerImages = [];
          setRetrievedCount(null);
          setStreamAnswerImages([]);
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
              skip_clarification: options?.skipClarification ?? false,
              doc_hints: options?.docHints ?? [],
            }),
          });
          if (!res.ok) {
            const body = await parseResponseBody(res);
            const httpError = classifyHttpError(res.status, body);
            if (httpError.kind === "auth" && httpError.httpStatus === 401) {
              applyAuthRedirect();
            }
            throw new StreamTerminalError(httpError);
          }

          if (attempt === 0) {
            setLoading(false);
            setStreaming(true);
          } else {
            showNetToast("online", "已重连", 3000);
          }

          const reader = res.body?.getReader();
          if (!reader) {
            throw new StreamTerminalError({
              kind: "stream_empty",
              code: "stream_empty",
              message: "服务暂时不可用，请稍后重试",
              status_code: null,
              endpoint: "",
              retryable: false,
              httpStatus: null,
            });
          }
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
                    handleStreamEvent(JSON.parse(data));
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
                handleStreamEvent(JSON.parse(data));
              } catch {}
            }
          }
          clearRequestTimeout();
          if (!streamDone) {
            if (receivedAnyDelta.current) {
              throw new StreamTerminalError({
                kind: "stream_truncated",
                code: "stream_truncated",
                message: "回答中断，已显示部分内容",
                status_code: null,
                endpoint: "",
                retryable: false,
                httpStatus: null,
              });
            }
            throw new StreamTerminalError({
              kind: "stream_empty",
              code: "stream_empty",
              message: "服务暂时不可用，请稍后重试",
              status_code: null,
              endpoint: "",
              retryable: false,
              httpStatus: null,
            });
          }
        } catch (error) {
          clearRequestTimeout();
          if (error instanceof StreamTerminalError) {
            streamError = error.error;
            if (streamError.kind === "auth" && streamError.httpStatus === 401) {
              applyAuthRedirect();
            }
            streamDone = true;
            break;
          }
          if (controller.signal.aborted || isAbortError(error)) {
            if (requestTimedOut) {
              const timeoutErrorInfo: StreamErrorInfo = {
                kind: "business",
                code: "timeout",
                message: "请求超时，请重试或换一个更简单的问题",
                status_code: null,
                endpoint: "",
                retryable: false,
                httpStatus: null,
              };
              streamError = timeoutErrorInfo;
              clearInterval(intervalId);
              await persistCurrentAnswer(timeoutErrorInfo.message);
              if (requestSeq === requestSeqRef.current) {
                setStreamPhase("done");
                setLoading(false);
                setStreaming(false);
                setStreamingMsgId(null);
                setStreamingConvId(null);
                abortRef.current = null;
              }
              return;
            }
            streamDone = true;
            break;
          }
          const classified = classifyFetchException(error);
          if (receivedAnyDelta.current && classified.kind === "network") {
            streamError = {
              kind: "interrupted",
              code: "unknown_error",
              message: "回答中断，已显示部分内容",
              status_code: null,
              endpoint: "",
              retryable: false,
              httpStatus: null,
            };
            streamDone = true;
            break;
          }
          streamError = classified;
          if (classified.kind === "network" && attempt < MAX_RETRIES) {
            continue;
          }
          streamDone = true;
          break;
        }
        if (streamDone) break;
      }

      clearInterval(intervalId);
      setStreamPhase("done");
      await persistCurrentAnswer();
      if (requestSeq === requestSeqRef.current) {
        setStreaming(false);
        setStreamingMsgId(null);
        setStreamingConvId(null);
        abortRef.current = null;
      }
    } catch (e) {
      clearInterval(intervalId);
      if (isAbortError(e)) {
        await persistCurrentAnswer();
        if (requestSeq === requestSeqRef.current) {
          setStreamPhase("done");
          setLoading(false);
          setStreaming(false);
          setStreamingMsgId(null);
          setStreamingConvId(null);
          abortRef.current = null;
        }
        return;
      }
      const networkErrorInfo = classifyFetchException(e);
      await updateConversation(
        convId,
        newMsgs.map((m) =>
          m.id === aiMsgId
            ? {
                ...m,
                content: networkErrorInfo.message,
                errorInfo: networkErrorInfo,
              }
            : m,
        ),
      );
      if (requestSeq === requestSeqRef.current) {
        setStreamPhase("done");
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
    streamPhase,
    retrievedCount,
    streamingConvId,
    reasoningSteps,
    causalChain,
    submit,
    cancel: () => abortRef.current?.abort(),
    setReasoningSteps,
    setCausalChain,
  };
}
