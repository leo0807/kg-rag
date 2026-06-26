"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useFavorites } from "@/app/favorites/useFavorites";
import type { NetToastType } from "@/components/NetToast";
import { fetchApi } from "@/lib/api";
import type { SourcePanelFilters, SourceSection, Strategy } from "./types";
import { useCompareQuery } from "./useCompareQuery";
import { useConversations } from "./useConversations";
import { useInlineQuestionEdit } from "./useInlineQuestionEdit";
import { useStreamQuery } from "./useStreamQuery";

const SOURCE_FILTERS_KEY = "query:source_panel_filters_by_conversation";

function defaultFilters(): SourcePanelFilters {
  return { sourceTypes: [], expandedOnly: false, traceFilters: [] };
}

export function useChat() {
  const conversations = useConversations();
  const {
    activeId,
    activeConv,
    setActiveId,
    createConversation,
    updateConversation,
    refetch,
  } = conversations;

  const [input, _setInput] = useState("");
  const [queuedQuestion, setQueuedQuestion] = useState<string | null>(null);
  const queuedQuestionRef = useRef<string | null>(null);
  const [pendingFollowUpDocHints, setPendingFollowUpDocHints] = useState<
    string[]
  >([]);
  const [strategy, setStrategy] = useState<Strategy>("parallel");
  const [useHyde, setUseHyde] = useState(false);
  const hydeAlpha = 0.5;
  const [pendingImages, setPendingImages] = useState<string[]>([]);
  const [quoteSource, setQuoteSource] = useState<SourceSection | null>(null);
  const [netToast, setNetToast] = useState<{
    type: NetToastType;
    label: string;
  } | null>(null);
  const [compareMode, setCompareMode] = useState(() =>
    typeof window !== "undefined"
      ? localStorage.getItem("query:compare_mode") === "1"
      : false,
  );
  const [filtersByConv, setFiltersByConv] = useState<
    Record<string, SourcePanelFilters>
  >(() => {
    if (typeof window === "undefined") return {};
    try {
      const raw = sessionStorage.getItem(SOURCE_FILTERS_KEY);
      return raw ? JSON.parse(raw) : {};
    } catch {
      return {};
    }
  });

  const {
    editingMessageIndex,
    editingMessageDraft,
    setEditingMessageDraft,
    startEdit: handleEditQuestion,
    cancelEdit: cancelEditQuestion,
  } = useInlineQuestionEdit();
  const isAdmin =
    typeof window !== "undefined"
      ? JSON.parse(localStorage.getItem("user") ?? "{}").is_admin === true
      : false;

  const { favorites, getFavoriteId, addFavorite, removeFavorite } =
    useFavorites();
  const favoritedChunkIds = new Set(
    favorites
      .filter((f) => f.type === "section" && Boolean(f.section_id))
      .flatMap((f) => (f.section_id ? [f.section_id] : [])),
  );

  const bottomRef = useRef<HTMLDivElement>(null);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const activeIdRef = useRef<string | null>(activeId);
  const conversationsRef = useRef(conversations.conversations);
  const deleteConvRef = useRef(conversations.deleteConversation);

  const showNetToast = useCallback(
    (type: NetToastType, label: string, autoDismissMs?: number) => {
      if (toastTimer.current) clearTimeout(toastTimer.current);
      setNetToast({ type, label });
      if (autoDismissMs) {
        toastTimer.current = setTimeout(() => setNetToast(null), autoDismissMs);
      }
    },
    [],
  );

  const stream = useStreamQuery({
    strategy,
    useHyde,
    hydeAlpha,
    activeId,
    activeConv,
    conversations: conversations.conversations,
    createConversation,
    updateConversation,
    showNetToast,
  });
  const currentConversationLoading =
    Boolean(activeId) && stream.streamingConvId === activeId && stream.loading;
  const currentConversationStreaming =
    Boolean(activeId) &&
    stream.streamingConvId === activeId &&
    stream.streaming;
  const currentConversationBusy =
    currentConversationLoading || currentConversationStreaming;

  const compareQuery = useCompareQuery();

  // Keep ref in sync so the effect below can read the latest queued value
  useEffect(() => {
    queuedQuestionRef.current = queuedQuestion;
  }, [queuedQuestion]);

  // When the current conversation finishes, auto-submit queued question
  useEffect(() => {
    if (currentConversationBusy || !queuedQuestionRef.current) return;
    const q = queuedQuestionRef.current;
    queuedQuestionRef.current = null;
    setQueuedQuestion(null);
    if (compareMode) void compareQuery.compare(q);
    else void stream.submit(q, [], { skipClarification: false, docHints: [] });
  }, [
    currentConversationBusy,
    compareMode,
    compareQuery.compare,
    stream.submit,
  ]);

  const setInput = useCallback((value: string) => {
    _setInput(value);
    setPendingFollowUpDocHints([]);
  }, []);

  useEffect(() => {
    activeIdRef.current = activeId;
  });
  useEffect(() => {
    conversationsRef.current = conversations.conversations;
  });
  useEffect(() => {
    deleteConvRef.current = conversations.deleteConversation;
  });

  useEffect(() => {
    const handle = () => {
      if (document.visibilityState !== "visible") return;
      const cid = activeIdRef.current;
      if (!cid) return;
      const conv = conversationsRef.current.find((c) => c.id === cid);
      if (conv && conv.messages.length === 0) deleteConvRef.current(cid);
    };
    document.addEventListener("visibilitychange", handle);
    return () => document.removeEventListener("visibilitychange", handle);
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  });

  useEffect(() => {
    const onOffline = () => showNetToast("offline", "网络已断开");
    const onOnline = () => showNetToast("online", "网络已恢复", 3000);
    window.addEventListener("offline", onOffline);
    window.addEventListener("online", onOnline);
    return () => {
      window.removeEventListener("offline", onOffline);
      window.removeEventListener("online", onOnline);
    };
  }, [showNetToast]);

  useEffect(() => {
    try {
      sessionStorage.setItem(SOURCE_FILTERS_KEY, JSON.stringify(filtersByConv));
    } catch {
      void 0;
    }
  }, [filtersByConv]);

  const activeSourceFilters = activeId
    ? (filtersByConv[activeId] ?? defaultFilters())
    : defaultFilters();

  function handleSourceFiltersChange(next: SourcePanelFilters) {
    if (!activeId) return;
    setFiltersByConv((prev) => ({ ...prev, [activeId]: next }));
  }

  function toggleCompareMode() {
    setCompareMode((v) => {
      const next = !v;
      localStorage.setItem("query:compare_mode", next ? "1" : "0");
      return next;
    });
  }

  async function handleSubmit() {
    if (
      (!input.trim() && pendingImages.length === 0) ||
      currentConversationBusy
    )
      return;
    const citation = quoteSource
      ? `> 引用章节：${quoteSource.doc_id} §${quoteSource.number}《${quoteSource.title}》\n\n`
      : "";
    const question = citation + input.trim();
    const images = [...pendingImages];
    setInput("");
    setPendingImages([]);
    setQuoteSource(null);
    await submitQuestion(question, images, {
      docHints: pendingFollowUpDocHints,
    });
    setPendingFollowUpDocHints([]);
  }

  async function submitQuestion(
    question: string,
    images: string[],
    options?: {
      skipClarification?: boolean;
      docHints?: string[];
      replaceFromIndex?: number;
    },
  ) {
    if (compareMode) await compareQuery.compare(question);
    else {
      await stream.submit(question, images, {
        replaceFromIndex: options?.replaceFromIndex,
        skipClarification: options?.skipClarification ?? false,
        docHints: options?.docHints ?? [],
      });
    }
  }

  async function submitEditedQuestion(messageIndex: number, content: string) {
    if (!activeConv) return;
    const original = activeConv.messages[messageIndex];
    if (!original || original.role !== "user") return;
    await stream.submit(content, original.images ?? [], {
      replaceFromIndex: messageIndex,
    });
    cancelEditQuestion();
  }

  async function handleClarificationSelect(
    _originalQuestion: string,
    option: string,
  ) {
    const refined = `请介绍${option}的工艺要求`;
    _setInput(refined);
    setPendingFollowUpDocHints([]);
    await submitQuestion(refined, [], { skipClarification: true });
    _setInput("");
  }

  function handleQueueQuestion(text: string) {
    setQueuedQuestion(text);
    queuedQuestionRef.current = text;
    setInput("");
  }

  function handleCancelQueue() {
    setQueuedQuestion(null);
    queuedQuestionRef.current = null;
  }

  async function handleRetryQuestion(
    question: string,
    images?: string[],
    replaceFromIndex?: number,
  ) {
    await submitQuestion(question, images ?? [], {
      skipClarification: false,
      ...(replaceFromIndex !== undefined ? { replaceFromIndex } : {}),
    });
  }

  function handleFollowUpSelect(question: string, sourceDocIds?: string[]) {
    _setInput(question);
    setPendingFollowUpDocHints(
      Array.from(
        new Set(
          (sourceDocIds ?? []).map((docId) => docId.trim()).filter(Boolean),
        ),
      ),
    );
  }

  async function handleBranch(upToIndex: number) {
    if (!activeConv || !activeId) return;
    try {
      const result = await fetchApi<{ id?: string }>("/api/conversations/branch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source_conversation_id: activeId,
          message_index: upToIndex,
        }),
      });
      if (result?.id) {
        await refetch();
        setActiveId(result.id);
      }
    } catch (e) {
      console.error("分支创建失败:", e);
    }
  }

  async function handleBranchCreated(branchId: string) {
    await refetch();
    setActiveId(branchId);
  }

  async function handleSourceClick(chunkId: string) {
    const stored = JSON.parse(localStorage.getItem("user") ?? "{}");
    const lastUser = activeConv?.messages.findLast((m) => m.role === "user");
    const lastAI = activeConv?.messages.findLast((m) => m.role === "assistant");
    await fetchApi("/api/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question: lastUser?.content ?? "",
        answer: lastAI?.content ?? "",
        sources: [],
        rating: 1,
        strategy,
        user_id: stored.user_id ?? "",
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
    const lines = [
      `# ${activeConv.title}`,
      ``,
      ...activeConv.messages.flatMap((m) => [
        m.role === "user" ? `**用户：** ${m.content}` : `**AI：** ${m.content}`,
        ``,
      ]),
      `---`,
      `*导出时间：${new Date().toLocaleString("zh-CN")}*`,
    ];
    const blob = new Blob([lines.join("\n")], {
      type: "text/markdown;charset=utf-8",
    });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${activeConv.title}_${Date.now()}.md`;
    a.click();
  }

  async function handleFavoriteSection(s: SourceSection) {
    const favId = getFavoriteId({ type: "section", section_id: s.chunk_id });
    if (favId) await removeFavorite(favId);
    else
      await addFavorite({
        type: "section",
        doc_id: s.doc_id,
        section_id: s.chunk_id,
        title: `§${s.number} ${s.title}`,
      });
  }

  return {
    ...conversations,
    input,
    setInput,
    strategy,
    setStrategy,
    useHyde,
    setUseHyde,
    pendingImages,
    setPendingImages,
    quoteSource,
    setQuoteSource,
    netToast,
    setNetToast,
    compareMode,
    setCompareMode,
    isAdmin,
    favoritedChunkIds,
    bottomRef,
    activeSourceFilters,
    stream,
    streamPhase: stream.streamPhase,
    currentConversationLoading,
    currentConversationStreaming,
    currentConversationBusy,
    compareQuery,
    handleSourceFiltersChange,
    toggleCompareMode,
    handleSubmit,
    handleBranch,
    handleBranchCreated,
    handleSourceClick,
    handleQuoteSource,
    exportConversation,
    handleFavoriteSection,
    editingMessageIndex,
    editingMessageDraft,
    setEditingMessageDraft,
    handleEditQuestion: (messageIndex: number, content: string) => {
      setQuoteSource(null);
      handleEditQuestion(messageIndex, content);
    },
    cancelEditQuestion,
    submitEditedQuestion,
    handleClarificationSelect,
    handleFollowUpSelect,
    handleRetryQuestion,
    showNetToast,
    queuedQuestion,
    handleQueueQuestion,
    handleCancelQueue,
  };
}
