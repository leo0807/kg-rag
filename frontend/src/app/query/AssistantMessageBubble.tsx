"use client";

import { AgentStepsPanel } from "./AgentStepsPanel";
import { AnswerImageGallery } from "./AnswerImageGallery";
import { AssistantFeedbackSection } from "./AssistantFeedbackSection";
import { AssistantMarkdown } from "./AssistantMarkdown";
import { AssistantMessageActions } from "./AssistantMessageActions";
import { AssistantMessageExtras } from "./AssistantMessageExtras";
import { ClarificationBubble } from "./ClarificationBubble";
import { FollowUpSuggestions } from "./FollowUpSuggestions";
import { MessageError } from "./MessageError";
import type {
  AgentStepInfo,
  AnswerImage,
  ClarificationInfo,
  LLMErrorInfo,
  QueryMetrics,
  SourceSection,
} from "./types";
import { useSourcePanelState } from "./useSourcePanelState";

interface Props {
  content: string;
  sources?: SourceSection[];
  streaming?: boolean;
  followUpQuestions?: string[];
  followUpDocIds?: string[];
  errorInfo?: LLMErrorInfo;
  expansionInfo?: string[];
  metrics?: QueryMetrics;
  isAdmin?: boolean;
  clarification?: ClarificationInfo;
  onSourceClick?: (chunkId: string) => void;
  onQuoteSource?: (source: SourceSection) => void;
  onBranch?: () => void;
  onFollowUp?: (q: string, sourceDocIds?: string[]) => void;
  onRetry?: () => void;
  onFavoriteSection?: (s: SourceSection) => void;
  favoritedChunkIds?: Set<string>;
  question?: string;
  strategy?: string;
  onLowScoreRetry?: (q: string) => void;
  onClarificationSelect?: (option: string) => void;
  agentSteps?: AgentStepInfo[];
  answerImages?: AnswerImage[];
  selectedAnswer?: string;
}

export function AssistantMessageBubble({
  content,
  sources,
  streaming,
  followUpQuestions,
  followUpDocIds,
  errorInfo,
  expansionInfo,
  metrics,
  isAdmin,
  clarification,
  onSourceClick,
  onQuoteSource,
  onBranch,
  onFollowUp,
  onRetry,
  onFavoriteSection,
  favoritedChunkIds,
  question,
  strategy,
  onLowScoreRetry,
  onClarificationSelect,
  agentSteps,
  answerImages,
  selectedAnswer,
}: Props) {
  const sourcePanelState = useSourcePanelState(sources);

  return (
    <div className="mb-6 flex justify-start">
      <div className="w-full max-w-[85%]">
        <div className="mb-2 flex items-center gap-2">
          <div className="flex h-6 w-6 items-center justify-center rounded-full border border-[#1B6BB5]/30 bg-[#1B6BB5]/20 text-xs font-bold text-[#1B6BB5] dark:text-[#5BA3E0]">
            AI
          </div>
          <span className="text-xs text-gray-600">CPS 知识库</span>
          {streaming && (
            <div className="ml-1 flex items-center gap-1">
              {[0, 150, 300].map((delay) => (
                <div
                  key={delay}
                  className="h-1 w-1 animate-bounce rounded-full bg-indigo-400"
                  style={{ animationDelay: `${delay}ms` }}
                />
              ))}
            </div>
          )}
          {!streaming && onBranch && (
            <button
              type="button"
              onClick={onBranch}
              className="ml-2 flex items-center gap-1 text-xs text-gray-600 transition-colors hover:text-indigo-400"
              title="从此处开始新的分支对话"
            >
              <svg
                aria-hidden="true"
                className="h-3 w-3"
                viewBox="0 0 12 12"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
              >
                <path d="M2 2v4a2 2 0 002 2h4M10 4l-2-2 2-2" />
              </svg>
              分支
            </button>
          )}
        </div>

        {errorInfo && (
          <MessageError
            errorInfo={errorInfo}
            isAdmin={isAdmin}
            onRetry={onRetry}
          />
        )}

        {!errorInfo && (
          <div className="group relative rounded-2xl rounded-tl-sm border border-gray-800 bg-gray-900 px-4 py-3 pr-12 pt-10">
            {clarification ? (
              <ClarificationBubble
                message={clarification.message}
                options={clarification.options}
                onSelect={(option) => onClarificationSelect?.(option)}
              />
            ) : (
              <>
                {agentSteps && agentSteps.length > 0 && (
                  <AgentStepsPanel steps={agentSteps} streaming={streaming} />
                )}
                {selectedAnswer && (
                  <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs text-emerald-300">
                    <span className="font-medium">最终答案</span>
                    <span className="rounded-full bg-emerald-500/20 px-2 py-0.5 font-semibold text-emerald-200">
                      {selectedAnswer}
                    </span>
                  </div>
                )}
                {!streaming && <AssistantMessageActions text={content} />}
                <AssistantMarkdown content={content} streaming={streaming} />

                {!streaming && answerImages && answerImages.length > 0 && (
                  <AnswerImageGallery
                    images={answerImages}
                    contextText={content}
                  />
                )}

                {!streaming && expansionInfo && expansionInfo.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {expansionInfo.map((info) => (
                      <span
                        key={info}
                        className="inline-flex items-center gap-1 rounded-md border border-violet-800/50 bg-violet-950/40 px-1.5 py-0.5 text-[10px] text-violet-300"
                      >
                        <span className="text-violet-500">扩展</span>
                        {info}
                      </span>
                    ))}
                  </div>
                )}

                {!streaming &&
                  followUpQuestions &&
                  followUpQuestions.length > 0 && (
                    <FollowUpSuggestions
                      questions={followUpQuestions}
                      sourceDocIds={followUpDocIds}
                      onFollowUp={onFollowUp}
                    />
                  )}

                {!streaming && sources && sources.length > 0 && (
                  <AssistantMessageExtras
                    content={content}
                    metrics={metrics}
                    onSourceClick={onSourceClick}
                    onQuoteSource={onQuoteSource}
                    onFavoriteSection={onFavoriteSection}
                    favoritedChunkIds={favoritedChunkIds}
                    state={sourcePanelState}
                  />
                )}
                {!streaming && (
                  <AssistantFeedbackSection
                    question={question}
                    content={content}
                    sources={sources}
                    strategy={strategy}
                    onLowScoreRetry={onLowScoreRetry}
                  />
                )}
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
