"use client";

import NetToast from "@/components/NetToast";
import { ChatPanel } from "./ChatPanel";
import ConversationInput from "./ConversationInput";
import ConversationSidebar from "./ConversationSidebar";
import { InputBar } from "./InputBar";
import { useChat } from "./useChat";

export default function QueryPage() {
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
    currentConversationLoading,
    currentConversationStreaming,
    compareQuery,
    handleSourceFiltersChange,
    toggleCompareMode,
    handleSubmit,
    handleBranch,
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

  function handleLowScoreRetry(q: string) {
    setStrategy("graph_augmented");
    setInput(q);
  }

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
        disableNew={activeConv !== null && historyLen === 0}
      />

      <div className="flex-1 flex flex-col min-w-0">
        <InputBar
          title={activeConv?.title ?? "选择或新建对话"}
          compareMode={compareMode}
          canExport={!!activeConv && historyLen > 0}
          onToggleCompare={toggleCompareMode}
          onExport={exportConversation}
        />

        <ChatPanel
          activeConv={activeConv}
          loading={stream.loading}
          streaming={stream.streaming}
          streamingMsgId={stream.streamingMsgId}
          reasoningSteps={stream.reasoningSteps}
          causalChain={stream.causalChain}
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
  );
}
