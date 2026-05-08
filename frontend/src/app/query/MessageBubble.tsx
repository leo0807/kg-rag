"use client";

import { AssistantMessageBubble } from "./AssistantMessageBubble";
import type {
  AgentStepInfo,
  ClarificationInfo,
  LLMErrorInfo,
  QueryMetrics,
  SourcePanelFilters,
  SourceSection,
} from "./types";
import { UserMessageBubble } from "./UserMessageBubble";

interface Props {
  role: "user" | "assistant";
  content: string;
  sources?: SourceSection[];
  images?: string[];
  streaming?: boolean;
  followUpQuestions?: string[];
  errorInfo?: LLMErrorInfo;
  expansionInfo?: string[];
  metrics?: QueryMetrics;
  isAdmin?: boolean;
  onSourceClick?: (chunkId: string) => void;
  onQuoteSource?: (source: SourceSection) => void;
  onBranch?: () => void;
  onEditQuestion?: () => void;
  isEditing?: boolean;
  editValue?: string;
  onEditChange?: (v: string) => void;
  onEditSubmit?: () => void;
  onEditCancel?: () => void;
  onFollowUp?: (q: string) => void;
  onRetry?: () => void;
  onFavoriteSection?: (s: SourceSection) => void;
  favoritedChunkIds?: Set<string>;
  sourcePanelFilters?: SourcePanelFilters;
  onSourcePanelFiltersChange?: (filters: SourcePanelFilters) => void;
  question?: string;
  strategy?: string;
  onLowScoreRetry?: (q: string) => void;
  clarification?: ClarificationInfo;
  onClarificationSelect?: (option: string) => void;
  agentSteps?: AgentStepInfo[];
}

export default function MessageBubble({
  role,
  content,
  sources,
  images,
  streaming,
  followUpQuestions,
  errorInfo,
  expansionInfo,
  metrics,
  isAdmin,
  onSourceClick,
  onQuoteSource,
  onBranch,
  onEditQuestion,
  isEditing,
  editValue,
  onEditChange,
  onEditSubmit,
  onEditCancel,
  onFollowUp,
  onRetry,
  onFavoriteSection,
  favoritedChunkIds,
  question,
  strategy,
  onLowScoreRetry,
  clarification,
  onClarificationSelect,
  agentSteps,
}: Props) {
  if (role === "user") {
    return (
      <UserMessageBubble
        content={content}
        images={images}
        onEditQuestion={onEditQuestion}
        isEditing={isEditing}
        editValue={editValue}
        onEditChange={onEditChange}
        onEditSubmit={onEditSubmit}
        onEditCancel={onEditCancel}
      />
    );
  }

  return (
    <AssistantMessageBubble
      content={content}
      sources={sources}
      streaming={streaming}
      followUpQuestions={followUpQuestions}
      errorInfo={errorInfo}
      expansionInfo={expansionInfo}
      metrics={metrics}
      isAdmin={isAdmin}
      onSourceClick={onSourceClick}
      onQuoteSource={onQuoteSource}
      onBranch={onBranch}
      onFollowUp={onFollowUp}
      onRetry={onRetry}
      onFavoriteSection={onFavoriteSection}
      favoritedChunkIds={favoritedChunkIds}
      question={question}
      strategy={strategy}
      onLowScoreRetry={onLowScoreRetry}
      clarification={clarification}
      onClarificationSelect={onClarificationSelect}
      agentSteps={agentSteps}
    />
  );
}
