"use client";

import type { RefObject } from "react";
import { ConversationMessages } from "./ConversationMessages";
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

export function ChatPanel(props: Props) {
  return <ConversationMessages {...props} />;
}
