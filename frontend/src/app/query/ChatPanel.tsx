"use client";

import { GitCompare } from "lucide-react";
import type { RefObject } from "react";
import SkeletonCard from "@/components/SkeletonCard";
import { CausalChainPanel } from "./CausalChainPanel";
import CompareGrid from "./CompareGrid";
import MessageBubble from "./MessageBubble";
import { ReasoningChain } from "./ReasoningChain";
import type { SourcePanelFilters, SourceSection, Strategy } from "./types";

function normalizeBubbleText(text: string) {
  return text.replace(/\u00A0/g, " ").replace(/[ \t]{3,}/g, " ");
}

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
}

export function ChatPanel({
  activeConv,
  loading,
  streaming,
  streamingMsgId,
  streamingText,
  reasoningSteps,
  causalChain,
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
            {activeConv.messages.map((msg, i) => (
              <div key={msg.id}>
                {msg.role === "assistant" &&
                  (msg.causalChain ? (
                    <CausalChainPanel
                      data={
                        msg.causalChain as Parameters<
                          typeof CausalChainPanel
                        >[0]["data"]
                      }
                    />
                  ) : streaming && msg.id === streamingMsgId && causalChain ? (
                    <CausalChainPanel
                      data={
                        causalChain as Parameters<
                          typeof CausalChainPanel
                        >[0]["data"]
                      }
                    />
                  ) : null)}
                <MessageBubble
                  role={msg.role}
                  content={normalizeBubbleText(
                    msg.role === "assistant" &&
                      streaming &&
                      msg.id === streamingMsgId
                      ? streamingText
                      : msg.content,
                  )}
                  sources={msg.sources}
                  images={msg.images}
                  streaming={streaming && msg.id === streamingMsgId}
                  followUpQuestions={
                    msg.role === "assistant" ? msg.followUpQuestions : undefined
                  }
                  expansionInfo={
                    msg.role === "assistant" ? msg.expansionInfo : undefined
                  }
                  metrics={msg.role === "assistant" ? msg.metrics : undefined}
                  errorInfo={
                    msg.role === "assistant"
                      ? (msg.errorInfo as Parameters<
                          typeof MessageBubble
                        >[0]["errorInfo"])
                      : undefined
                  }
                  isAdmin={isAdmin}
                  onSourceClick={onSourceClick}
                  onQuoteSource={onQuoteSource}
                  onBranch={
                    msg.role === "assistant" && !streaming
                      ? () => onBranch(i)
                      : undefined
                  }
                  onFollowUp={(q) => setInput(q)}
                  onRetry={
                    msg.role === "assistant" && msg.errorInfo
                      ? () => {
                          const prev = activeConv.messages[i - 1];
                          if (prev?.role === "user") setInput(prev.content);
                        }
                      : undefined
                  }
                  onEditQuestion={
                    msg.role === "user"
                      ? () => onEditQuestion(i, msg.content)
                      : undefined
                  }
                  favoritedChunkIds={favoritedChunkIds}
                  sourcePanelFilters={
                    msg.role === "assistant" ? activeSourceFilters : undefined
                  }
                  onSourcePanelFiltersChange={
                    msg.role === "assistant" ? onSourceFiltersChange : undefined
                  }
                  onFavoriteSection={onFavoriteSection}
                  question={
                    msg.role === "assistant"
                      ? activeConv.messages[i - 1]?.content
                      : undefined
                  }
                  strategy={msg.role === "assistant" ? strategy : undefined}
                  onLowScoreRetry={
                    msg.role === "assistant" ? onLowScoreRetry : undefined
                  }
                />
              </div>
            ))}
          </>
        )}
        {loading && <SkeletonCard />}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
