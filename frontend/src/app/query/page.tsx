"use client";

import NetToast from "@/components/NetToast";
import ConversationSidebar from "./ConversationSidebar";
import ConversationInput from "./ConversationInput";
import { InputBar } from "./InputBar";
import { ChatPanel } from "./ChatPanel";
import { useChat } from "./useChat";

export default function QueryPage() {
  const chat = useChat();
  const {
    conversations, activeId, activeConv, setActiveId, createConversation,
    deleteConversation, clearConversation,
    input, setInput, strategy, setStrategy, useHyde, setUseHyde,
    pendingImages, setPendingImages, quoteSource, setQuoteSource,
    netToast, setNetToast, compareMode, isAdmin, favoritedChunkIds, bottomRef,
    activeSourceFilters, stream, compareQuery,
    handleSourceFiltersChange, toggleCompareMode, handleSubmit,
    handleBranch, handleSourceClick, handleQuoteSource, exportConversation,
    handleFavoriteSection,
  } = chat;

  const historyLen = activeConv?.messages.length ?? 0;

  return (
    <div className="flex h-full bg-gray-950">
      {netToast && (
        <NetToast type={netToast.type} label={netToast.label} onClose={() => setNetToast(null)} />
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
          isAdmin={isAdmin}
          favoritedChunkIds={favoritedChunkIds}
          activeSourceFilters={activeSourceFilters}
          bottomRef={bottomRef}
          setInput={setInput}
          setStrategy={setStrategy}
          toggleCompareMode={toggleCompareMode}
          onRetryStrategy={compareQuery.retryStrategy}
          onSourceClick={handleSourceClick}
          onQuoteSource={handleQuoteSource}
          onBranch={handleBranch}
          onSourceFiltersChange={handleSourceFiltersChange}
          onFavoriteSection={handleFavoriteSection}
        />

        <ConversationInput
          value={input}
          strategy={strategy}
          useHyde={useHyde}
          loading={stream.loading}
          streaming={stream.streaming}
          historyLen={historyLen}
          pendingImages={pendingImages}
          quoteSource={quoteSource}
          onChange={setInput}
          onStrategy={setStrategy}
          onHydeToggle={setUseHyde}
          onSubmit={handleSubmit}
          onClear={clearConversation}
          onAddImages={(imgs) => setPendingImages((prev) => [...prev, ...imgs])}
          onRemoveImage={(idx) => setPendingImages((prev) => prev.filter((_, i) => i !== idx))}
          onClearQuote={() => setQuoteSource(null)}
        />
      </div>
    </div>
  );
}
