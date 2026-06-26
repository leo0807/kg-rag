"use client";

import { useEffect, useRef, useState } from "react";
import NetToast from "@/components/NetToast";
import { ChatPanel } from "./ChatPanel";
import ConversationInput from "./ConversationInput";
import ConversationSidebar from "./ConversationSidebar";
import { InputBar } from "./InputBar";
import { useChat } from "./useChat";
import { useKeyboardShortcuts } from "./useKeyboardShortcuts";

export default function QueryPage() {
  const [mobileConversationOpen, setMobileConversationOpen] = useState(false);
  const chat = useChat();
  const {
    conversations,
    activeId,
    activeConv,
    setActiveId,
    createConversation,
    deleteConversation,
    clearConversation,
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
    isAdmin,
    favoritedChunkIds,
    bottomRef,
    activeSourceFilters,
    stream,
    streamPhase,
    retrievedCount,
    currentConversationLoading,
    currentConversationStreaming,
    compareQuery,
    handleSourceFiltersChange,
    toggleCompareMode,
    handleSubmit,
    handleBranch,
    handleBranchCreated,
    handleRetryQuestion,
    handleSourceClick,
    handleQuoteSource,
    exportConversation,
    handleFavoriteSection,
    editingMessageIndex,
    editingMessageDraft,
    setEditingMessageDraft,
    handleEditQuestion,
    cancelEditQuestion,
    submitEditedQuestion,
    handleClarificationSelect,
    handleFollowUpSelect,
    queuedQuestion,
    handleQueueQuestion,
    handleCancelQueue,
  } = chat;

  const historyLen = activeConv?.messages.length ?? 0;
  const inputAreaRef = useRef<HTMLDivElement>(null);

  // Draft auto-save: restore on mount, save on every change
  useEffect(() => {
    const saved = localStorage.getItem("query:draft");
    if (saved && !input) setInput(saved);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => {
    if (input) localStorage.setItem("query:draft", input);
    else localStorage.removeItem("query:draft");
  }, [input]);

  useKeyboardShortcuts({
    onNewConversation: () => createConversation(),
    onFocusInput: () => inputAreaRef.current?.querySelector("textarea")?.focus(),
    onStop: stream.cancel,
    streaming: currentConversationStreaming,
  });

  function handleLowScoreRetry(q: string) {
    setStrategy("graph_augmented");
    setInput(q);
  }

  return (
    <div className="relative flex h-full bg-gray-950">
      {netToast && (
        <NetToast
          type={netToast.type}
          label={netToast.label}
          onClose={() => setNetToast(null)}
        />
      )}
      <div className="hidden md:flex shrink-0">
        <ConversationSidebar
          conversations={conversations}
          activeId={activeId}
          onSelect={setActiveId}
          onDelete={deleteConversation}
          onNew={() => createConversation()}
          disableNew={activeConv !== null && historyLen === 0}
        />
      </div>

      <button
        type="button"
        aria-label="关闭会话列表"
        className={`fixed inset-0 z-40 bg-black/60 transition-opacity md:hidden ${
          mobileConversationOpen
            ? "opacity-100"
            : "pointer-events-none opacity-0"
        }`}
        onClick={() => setMobileConversationOpen(false)}
      />
      <div
        className={`fixed inset-y-0 left-0 z-50 transition-transform duration-200 md:hidden ${
          mobileConversationOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <ConversationSidebar
          mobile
          conversations={conversations}
          activeId={activeId}
          onSelect={(id) => {
            setActiveId(id);
            setMobileConversationOpen(false);
          }}
          onDelete={deleteConversation}
          onNew={() => createConversation()}
          disableNew={activeConv !== null && historyLen === 0}
          onClose={() => setMobileConversationOpen(false)}
        />
      </div>

      <div className="flex-1 flex flex-col min-w-0">
        <InputBar
          title={activeConv?.title ?? "选择或新建对话"}
          compareMode={compareMode}
          canExport={!!activeConv && historyLen > 0}
          onToggleCompare={toggleCompareMode}
          onExport={exportConversation}
          onOpenConversationSidebar={() => setMobileConversationOpen(true)}
        />

        <ChatPanel
          activeConv={activeConv}
          loading={stream.loading}
          streaming={stream.streaming}
          streamingMsgId={stream.streamingMsgId}
          reasoningSteps={stream.reasoningSteps}
          causalChain={stream.causalChain}
          streamPhase={streamPhase}
          retrievedCount={retrievedCount}
          compareMode={compareMode}
          compareLoading={compareQuery.loading}
          compareQuestion={compareQuery.question}
          compareResults={compareQuery.results}
          retryingStrategy={compareQuery.retryingStrategy}
          streamingText={stream.streamingText}
          isAdmin={isAdmin}
          favoritedChunkIds={favoritedChunkIds}
          activeSourceFilters={activeSourceFilters}
          bottomRef={bottomRef}
          strategy={strategy}
          setInput={setInput}
          toggleCompareMode={toggleCompareMode}
          onRetryStrategy={compareQuery.retryStrategy}
          onSourceClick={handleSourceClick}
          onQuoteSource={handleQuoteSource}
          onBranch={handleBranch}
          onBranchCreated={handleBranchCreated}
          onEditQuestion={handleEditQuestion}
          onSourceFiltersChange={handleSourceFiltersChange}
          onFavoriteSection={handleFavoriteSection}
          onLowScoreRetry={handleLowScoreRetry}
          editingMessageIndex={editingMessageIndex}
          editingMessageDraft={editingMessageDraft}
          onEditDraftChange={setEditingMessageDraft}
          onEditCancel={cancelEditQuestion}
          onEditSubmit={submitEditedQuestion}
          onClarificationSelect={handleClarificationSelect}
          onFollowUpSelect={handleFollowUpSelect}
          onRetryMessage={handleRetryQuestion}
        />

        <div ref={inputAreaRef}>
        <ConversationInput
          value={input}
          loading={currentConversationLoading}
          streaming={currentConversationStreaming}
          onStop={stream.cancel}
          pendingImages={pendingImages}
          quoteSource={quoteSource}
          onChange={setInput}
          onSubmit={handleSubmit}
          onClear={clearConversation}
          onAddImages={(imgs) => setPendingImages((prev) => [...prev, ...imgs])}
          onRemoveImage={(idx) =>
            setPendingImages((prev) => prev.filter((_, i) => i !== idx))
          }
          onClearQuote={() => setQuoteSource(null)}
          strategy={strategy}
          onStrategy={setStrategy}
          useHyde={useHyde}
          onHydeToggle={setUseHyde}
          historyLen={historyLen}
          queuedQuestion={queuedQuestion}
          onQueueQuestion={handleQueueQuestion}
          onCancelQueue={handleCancelQueue}
        />
        </div>
      </div>
    </div>
  );
}
