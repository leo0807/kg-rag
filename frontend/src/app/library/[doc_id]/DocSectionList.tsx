"use client";

import { ChevronDown, ChevronUp, Loader2, Star } from "lucide-react";
import type { MouseEvent } from "react";
import { LatexContent } from "@/components/LatexContent";
import type { Section, SectionContent } from "./useDocDetailTypes";

function highlight(text: string, keyword: string) {
  if (!keyword) return <>{text}</>;
  const idx = text.toLowerCase().indexOf(keyword.toLowerCase());
  if (idx === -1) return <>{text}</>;
  return (
    <>
      {text.slice(0, idx)}
      <mark className="bg-indigo-500/30 text-indigo-300 rounded px-0.5">
        {text.slice(idx, idx + keyword.length)}
      </mark>
      {text.slice(idx + keyword.length)}
    </>
  );
}

interface Props {
  visibleSections: Section[];
  sectionSearch: string;
  setSectionSearch: (v: string) => void;
  expandedChunk: string | null;
  loadingChunk: string | null;
  activeChunk: string | null;
  sectionContent: Record<string, SectionContent>;
  sectionRowRefs: { current: Map<string, HTMLDivElement> };
  onNavigate: (section: Section) => void;
  onToggleExpand: (section: Section) => void;
  onToggleFavorite: (e: MouseEvent, section: Section) => void;
  getFavoriteId: (opts: {
    type: string;
    section_id?: string;
  }) => string | null | undefined;
}

export function DocSectionList({
  visibleSections,
  sectionSearch,
  setSectionSearch,
  expandedChunk,
  loadingChunk,
  activeChunk,
  sectionContent,
  sectionRowRefs,
  onNavigate,
  onToggleExpand,
  onToggleFavorite,
  getFavoriteId,
}: Props) {
  return (
    <>
      <div className="flex items-center justify-between mb-3">
        <div className="text-xs text-gray-500">
          {sectionSearch && `匹配 ${visibleSections.length} 个`}
        </div>
        <input
          value={sectionSearch}
          onChange={(e) => setSectionSearch(e.target.value)}
          placeholder="搜索章节..."
          className="px-2.5 py-1 bg-gray-900 border border-gray-700 rounded
                     text-xs text-gray-200 outline-none focus:border-indigo-500
                     placeholder-gray-500 w-36"
        />
      </div>
      <div className="space-y-0.5">
        {visibleSections.map((section) => {
          const isExpanded = expandedChunk === section.chunk_id;
          const isLoading = loadingChunk === section.chunk_id;
          const isActive = activeChunk === section.chunk_id;
          const content = sectionContent[section.chunk_id];
          const favId = getFavoriteId({
            type: "section",
            section_id: section.chunk_id,
          });
          return (
            <div
              key={section.chunk_id}
              id={`section-${section.chunk_id}`}
              ref={(node) => {
                if (node) sectionRowRefs.current.set(section.chunk_id, node);
                else sectionRowRefs.current.delete(section.chunk_id);
              }}
              data-chunk-id={section.chunk_id}
            >
              <div
                className={`flex items-center group rounded-lg border transition-colors ${
                  isActive
                    ? "bg-gray-900 border-indigo-500/70 shadow-[0_0_0_1px_rgba(99,102,241,0.35)]"
                    : "border-transparent hover:bg-gray-900"
                }`}
              >
                <button
                  type="button"
                  onClick={() => onNavigate(section)}
                  className="flex-1 flex items-baseline gap-3 px-3 py-2.5 text-left min-w-0"
                  aria-current={isActive ? "true" : undefined}
                >
                  <span
                    className={`text-xs font-mono w-12 shrink-0 ${isActive ? "text-indigo-300" : "text-gray-500"}`}
                  >
                    {section.number}
                  </span>
                  <span
                    className={`text-sm flex-1 min-w-0 ${isActive ? "text-white" : "text-gray-300"}`}
                  >
                    {highlight(section.title, sectionSearch)}
                  </span>
                  <span
                    className={`shrink-0 ${isActive ? "text-indigo-300" : "text-gray-600 opacity-0 group-hover:opacity-100"}`}
                  >
                    {typeof section.page_idx === "number"
                      ? `P${section.page_idx + 1}`
                      : ""}
                  </span>
                </button>
                <button
                  type="button"
                  onClick={() => void onToggleExpand(section)}
                  title={isExpanded ? "收起章节内容" : "展开章节内容"}
                  className={`px-2 py-2.5 shrink-0 transition-colors ${
                    isActive
                      ? "text-indigo-300 hover:text-white"
                      : "text-gray-600 hover:text-gray-300"
                  }`}
                >
                  {isLoading ? (
                    <Loader2 size={12} className="animate-spin" />
                  ) : isExpanded ? (
                    <ChevronUp size={12} />
                  ) : (
                    <ChevronDown size={12} />
                  )}
                </button>
                <button
                  type="button"
                  onClick={(e) => onToggleFavorite(e, section)}
                  title={favId ? "取消收藏" : "收藏此章节"}
                  className="px-2 py-2.5 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity"
                >
                  <Star
                    size={13}
                    className={
                      favId
                        ? "text-amber-400 fill-amber-400"
                        : "text-gray-600 hover:text-amber-400"
                    }
                  />
                </button>
              </div>
              {isExpanded && (
                <div className="mx-3 mb-2 px-4 py-3 bg-gray-900 rounded-lg border border-gray-800 text-sm text-gray-400 leading-relaxed whitespace-pre-wrap">
                  {content ? (
                    <LatexContent content={content.content} />
                  ) : (
                    <div className="flex items-center gap-2 text-gray-500">
                      <Loader2 size={14} className="animate-spin" />
                      正在加载章节内容...
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </>
  );
}
