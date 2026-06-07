"use client";
import { GitCompare } from "lucide-react";
import type { RefObject } from "react";
import SkeletonCard from "@/components/SkeletonCard";
import CompareGrid from "./CompareGrid";
import { ConversationMessageList } from "./ConversationMessageList";
import { ProgressIndicator } from "./ProgressIndicator";
import { ReasoningChain } from "./ReasoningChain";
import type {
  AgentStepInfo,
  SourcePanelFilters,
  SourceSection,
  Strategy,
} from "./types";

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
    clarification?: import("./types").ClarificationInfo;
    agentSteps?: AgentStepInfo[];
  }[];
}

interface Props {
  activeConv: Conversation | null;
  loading: boolean;
  streaming: boolean;
  streamingMsgId: string | null;
  streamingText: string;
  streamPhase: import("./ProgressIndicator").StreamPhase;
  retrievedCount: number | null;
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
  onFollowUpSelect: (q: string, sourceDocIds?: string[]) => void;
  onRetryMessage: (
    q: string,
    images?: string[],
    replaceFromIndex?: number,
  ) => void;
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
  streamPhase,
  retrievedCount,
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
  onFollowUpSelect,
  onRetryMessage,
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
          <div className="flex flex-col items-center justify-center min-h-64 gap-4 py-10 px-4">
            <div className="text-5xl">✈️</div>
            <div className="text-gray-500 text-sm">开始提问关于航空工艺规范的问题</div>
            <div className="text-xs text-gray-700 text-center">
              <span className="font-mono bg-gray-900 border border-gray-800 px-1.5 py-0.5 rounded">⌘K</span>
              {" "}聚焦输入框 &nbsp;·&nbsp;
              <span className="font-mono bg-gray-900 border border-gray-800 px-1.5 py-0.5 rounded">⌘N</span>
              {" "}新建对话
            </div>
            <div className="flex flex-wrap justify-center gap-2 mt-1 max-w-md">
              {["铝合金焊接有哪些工艺要求？", "CPS 中对表面粗糙度有什么规定？", "复合材料修复的温度范围是多少？"].map(q => (
                <button key={q} type="button" onClick={() => setInput(q)}
                  className="text-xs px-3 py-1.5 bg-gray-900 border border-gray-800 rounded-full text-gray-400 hover:border-indigo-600 hover:text-indigo-300 transition-colors">
                  {q}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <>
            <ProgressIndicator
              phase={streamPhase}
              retrievedCount={retrievedCount}
            />
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
              onFollowUpSelect={onFollowUpSelect}
              onRetryMessage={onRetryMessage}
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
