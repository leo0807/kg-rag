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
  } = conversations;

  const [input, setInput] = useState("");
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
    await submitQuestion(question, images);
  }

  async function submitQuestion(question: string, images: string[]) {
    if (compareMode) await compareQuery.compare(question);
    else {
      await stream.submit(question, images);
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
    originalQuestion: string,
    option: string,
  ) {
    const refined = `${originalQuestion}，具体关于${option}`;
    setInput(refined);
    await submitQuestion(refined, []);
    setInput("");
  }

  async function handleBranch(upToIndex: number) {
    if (!activeConv) return;
    const msgs = activeConv.messages.slice(0, upToIndex + 1);
    const title = `分支: ${msgs[0]?.content?.slice(0, 18) || "新分支"}`;
    try {
      const conv = await fetchApi<{ id?: string }>("/api/conversations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title, strategy, messages: msgs }),
      });
      if (conv?.id) setActiveId(conv.id);
    } catch (e) {
      console.error("分支创建失败:", e);
    }
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
    currentConversationLoading,
    currentConversationStreaming,
    currentConversationBusy,
    compareQuery,
    handleSourceFiltersChange,
    toggleCompareMode,
    handleSubmit,
    handleBranch,
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
    showNetToast,
  };
}
