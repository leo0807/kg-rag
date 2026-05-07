"use client";
import { GitCompare } from "lucide-react";
import type { RefObject } from "react";
import SkeletonCard from "@/components/SkeletonCard";
import CompareGrid from "./CompareGrid";
import { ConversationMessageList } from "./ConversationMessageList";
import { ReasoningChain } from "./ReasoningChain";
import type { SourcePanelFilters, SourceSection, Strategy } from "./types";

interface Conversation {
  messages: {
    id: string;
    role: "user" | "assistant";
    content: string;
    sources?: SourceSection[];
    images?: string[];
    followUpQuestions?: string[];
    expansionInfo?: string[];
    errorInfo?: unknown;
    causalChain?: unknown;
    metrics?: import("./types").QueryMetrics;
  }[];
}

interface Props {
  activeConv: Conversation | null;
  loading: boolean;
  streaming: boolean;
  streamingMsgId: string | null;
  streamingText: string;
  reasoningSteps: unknown[];
  causalChain: unknown;
  compareMode: boolean;
  compareLoading: boolean;
  compareQuestion: string;
  compareResults: unknown[];
  retryingStrategy: string | null;
  isAdmin: boolean;
  favoritedChunkIds: Set<string>;
  activeSourceFilters: SourcePanelFilters;
  bottomRef: RefObject<HTMLDivElement | null>;
  strategy: Strategy;
  setInput: (v: string) => void;
  onLowScoreRetry?: (q: string) => void;
  toggleCompareMode: () => void;
  onRetryStrategy: (s: string) => void;
  onSourceClick: (chunkId: string) => void;
  onQuoteSource: (source: SourceSection) => void;
  onBranch: (idx: number) => void;
  onEditQuestion: (idx: number, content: string) => void;
  onSourceFiltersChange: (f: SourcePanelFilters) => void;
  onFavoriteSection: (s: SourceSection) => void;
  editingMessageIndex: number | null;
  editingMessageDraft: string;
  onEditDraftChange: (v: string) => void;
  onEditCancel: () => void;
  onEditSubmit: (idx: number, content: string) => void;
  onClarificationSelect: (originalQuestion: string, option: string) => void;
}

export function ConversationMessages({
  activeConv,
  loading,
  streaming,
  streamingMsgId,
  streamingText,
  reasoningSteps,
  compareMode,
  compareLoading,
  compareQuestion,
  compareResults,
  retryingStrategy,
  isAdmin,
  favoritedChunkIds,
  activeSourceFilters,
  bottomRef,
  strategy,
  setInput,
  toggleCompareMode,
  onRetryStrategy,
  onSourceClick,
  onQuoteSource,
  onBranch,
  onEditQuestion,
  onSourceFiltersChange,
  onFavoriteSection,
  onLowScoreRetry,
  editingMessageIndex,
  editingMessageDraft,
  onEditDraftChange,
  onEditCancel,
  onEditSubmit,
  onClarificationSelect,
}: Props) {
  const historyLen = activeConv?.messages.length ?? 0;

  return (
    <div className="flex-1 overflow-auto px-4 py-6">
      <div className="max-w-3xl mx-auto">
        {compareMode ? (
          <>
            {!compareLoading && compareResults.length === 0 && (
              <div className="flex flex-col items-center justify-center min-h-40 gap-3 py-8 text-gray-600">
                <GitCompare size={32} className="opacity-40" />
                <p className="text-sm">输入问题，对比四种检索策略的回答</p>
              </div>
            )}
            <CompareGrid
              question={compareQuestion}
              results={
                compareResults as Parameters<typeof CompareGrid>[0]["results"]
              }
              loading={compareLoading}
              retryingStrategy={retryingStrategy}
              onRetryStrategy={onRetryStrategy}
              onUseAnswer={(answer) => {
                toggleCompareMode();
                localStorage.setItem("query:compare_mode", "0");
                setInput(answer.slice(0, 200));
              }}
            />
          </>
        ) : !activeConv || historyLen === 0 ? (
          <div className="flex flex-col items-center justify-center min-h-64 gap-5 py-10">
            <div className="text-5xl">✈️</div>
            <div className="text-gray-500 text-sm">
              开始提问关于航空工艺规范的问题
            </div>
          </div>
        ) : (
          <>
            <ReasoningChain
              steps={
                reasoningSteps as Parameters<typeof ReasoningChain>[0]["steps"]
              }
            />
            <ConversationMessageList
              activeConv={activeConv}
              streaming={streaming}
              streamingMsgId={streamingMsgId}
              streamingText={streamingText}
              isAdmin={isAdmin}
              favoritedChunkIds={favoritedChunkIds}
              activeSourceFilters={activeSourceFilters}
              strategy={strategy}
              setInput={setInput}
              onLowScoreRetry={onLowScoreRetry}
              onSourceClick={onSourceClick}
              onQuoteSource={onQuoteSource}
              onBranch={onBranch}
              onEditQuestion={onEditQuestion}
              onSourceFiltersChange={onSourceFiltersChange}
              onFavoriteSection={onFavoriteSection}
              editingMessageIndex={editingMessageIndex}
              editingMessageDraft={editingMessageDraft}
              onEditDraftChange={onEditDraftChange}
              onEditCancel={onEditCancel}
              onEditSubmit={onEditSubmit}
              onClarificationSelect={onClarificationSelect}
            />
          </>
        )}
        {loading && <SkeletonCard />}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
