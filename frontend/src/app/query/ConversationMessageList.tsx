"use client";

import { CausalChainPanel } from "./CausalChainPanel";
import MessageBubble from "./MessageBubble";
import type {
  AgentStepInfo,
  AnswerImage,
  ClarificationInfo,
  SourcePanelFilters,
  SourceSection,
  Strategy,
} from "./types";

interface Props {
  activeConv: {
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
      clarification?: ClarificationInfo;
      agentSteps?: AgentStepInfo[];
      answerImages?: AnswerImage[];
    }[];
  };
  streaming: boolean;
  streamingMsgId: string | null;
  streamingText: string;
  isAdmin: boolean;
  favoritedChunkIds: Set<string>;
  activeSourceFilters: SourcePanelFilters;
  strategy: Strategy;
  onFollowUpSelect: (q: string, sourceDocIds?: string[]) => void;
  onRetryMessage: (
    q: string,
    images?: string[],
    replaceFromIndex?: number,
  ) => void;
  onLowScoreRetry?: (q: string) => void;
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

function normalizeBubbleText(text: string) {
  return text.replace(/\u00A0/g, " ").replace(/[ \t]{3,}/g, " ");
}

export function ConversationMessageList({
  activeConv,
  streaming,
  streamingMsgId,
  streamingText,
  isAdmin,
  favoritedChunkIds,
  activeSourceFilters,
  strategy,
  onFollowUpSelect,
  onRetryMessage,
  onLowScoreRetry,
  onSourceClick,
  onQuoteSource,
  onBranch,
  onEditQuestion,
  onSourceFiltersChange,
  onFavoriteSection,
  editingMessageIndex,
  editingMessageDraft,
  onEditDraftChange,
  onEditCancel,
  onEditSubmit,
  onClarificationSelect,
}: Props) {
  if (!activeConv) return null;
  return (
    <>
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
            ) : streaming && msg.id === streamingMsgId && msg.causalChain ? (
              <CausalChainPanel
                data={
                  msg.causalChain as Parameters<
                    typeof CausalChainPanel
                  >[0]["data"]
                }
              />
            ) : null)}
          <MessageBubble
            role={msg.role}
            content={normalizeBubbleText(
              msg.role === "assistant" && streaming && msg.id === streamingMsgId
                ? streamingText
                : msg.content,
            )}
            sources={msg.sources}
            images={msg.images}
            streaming={streaming && msg.id === streamingMsgId}
            followUpQuestions={
              msg.role === "assistant" ? msg.followUpQuestions : undefined
            }
            followUpDocIds={
              msg.role === "assistant"
                ? Array.from(
                    new Set(
                      (msg.sources ?? [])
                        .map((s) => s.doc_id)
                        .filter((doc_id): doc_id is string => Boolean(doc_id)),
                    ),
                  )
                : undefined
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
            onFollowUp={(q, sourceDocIds) => onFollowUpSelect(q, sourceDocIds)}
            onRetry={
              msg.role === "assistant" && msg.errorInfo
                ? () => {
                    const prev = activeConv.messages[i - 1];
                    if (prev?.role === "user")
                      onRetryMessage(prev.content, prev.images, i - 1);
                  }
                : undefined
            }
            onEditQuestion={
              msg.role === "user"
                ? () => onEditQuestion(i, msg.content)
                : undefined
            }
            onResend={
              msg.role === "user" && activeConv.messages[i + 1]?.errorInfo
                ? () => onRetryMessage(msg.content, msg.images, i)
                : undefined
            }
            isEditing={msg.role === "user" && editingMessageIndex === i}
            editValue={
              msg.role === "user" && editingMessageIndex === i
                ? editingMessageDraft
                : undefined
            }
            onEditChange={onEditDraftChange}
            onEditCancel={onEditCancel}
            onEditSubmit={
              msg.role === "user" && editingMessageIndex === i
                ? () => onEditSubmit(i, editingMessageDraft)
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
            clarification={
              msg.role === "assistant" ? msg.clarification : undefined
            }
            agentSteps={msg.role === "assistant" ? msg.agentSteps : undefined}
            answerImages={
              msg.role === "assistant" ? msg.answerImages : undefined
            }
            onClarificationSelect={
              msg.role === "assistant"
                ? (option) =>
                    onClarificationSelect(
                      activeConv.messages[i - 1]?.content ?? "",
                      option,
                    )
                : undefined
            }
          />
        </div>
      ))}
    </>
  );
}
