"use client";

import { ArrowLeft, Download, FileText } from "lucide-react";
import type { MouseEvent, RefObject } from "react";
import { DocSectionList } from "./DocSectionList";
import { DrawingsTab } from "./DrawingsTab";
import { ReprocessPanel } from "./ReprocessPanel";
import type {
  DocumentDetail,
  Section,
  SectionContent,
} from "./useDocDetailTypes";

interface Props {
  doc: DocumentDetail;
  docId: string;
  scrollContainerRef: RefObject<HTMLDivElement>;
  pdfUrl: string | null;
  downloadUrl: string | null;
  isAdmin: boolean;
  showPdf: boolean;
  activeTab: "sections" | "drawings" | "reprocess";
  expandedChunk: string | null;
  activeChunk: string | null;
  sectionContent: Record<string, SectionContent>;
  loadingChunk: string | null;
  sectionSearch: string;
  visibleSections: Section[];
  sectionRowRefs: RefObject<Map<string, HTMLDivElement>>;
  targetImageId?: string;
  refresh: () => void;
  handleDownload: () => void;
  setShowPdf: (v: boolean | ((prev: boolean) => boolean)) => void;
  setActiveTab: (v: "sections" | "drawings" | "reprocess") => void;
  setSectionSearch: (v: string) => void;
  onNavigate: (section: Section) => void;
  onToggleExpand: (section: Section) => Promise<void>;
  onToggleFavorite: (
    e: MouseEvent,
    section: { chunk_id: string; title: string; number: string },
  ) => Promise<void>;
  getFavoriteId: (args: {
    type: "section";
    section_id: string;
  }) => string | null;
}

export function DocumentDetailPanel({
  doc,
  docId,
  scrollContainerRef,
  pdfUrl,
  downloadUrl,
  isAdmin,
  showPdf,
  activeTab,
  expandedChunk,
  activeChunk,
  sectionContent,
  loadingChunk,
  sectionSearch,
  visibleSections,
  sectionRowRefs,
  targetImageId,
  refresh,
  handleDownload,
  setShowPdf,
  setActiveTab,
  setSectionSearch,
  onNavigate,
  onToggleExpand,
  onToggleFavorite,
  getFavoriteId,
}: Props) {
  return (
    <div
      ref={scrollContainerRef}
      className="bg-gray-950 overflow-y-auto p-8 max-w-3xl min-h-screen"
    >
      <div className={showPdf ? "px-6 pt-5 pb-4" : "mb-6"}>
        <a
          href="/library"
          className="inline-flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-300 transition-colors"
        >
          <ArrowLeft size={14} /> 返回文档库
        </a>
      </div>
      <div className={showPdf ? "px-6 pb-4 border-b border-gray-800" : "mb-8"}>
        <div className="text-sm font-mono text-indigo-400 mb-1">
          {doc.doc_id} · 版本 {doc.version || "—"}
        </div>
        <h1 className="text-xl font-semibold text-white leading-snug">
          {doc.title || "未命名文档"}
        </h1>
        <div className="text-sm text-gray-500 mt-1">
          发布日期：{doc.issue_date || "—"}
        </div>
        <div className="flex items-center gap-2 mt-3">
          {pdfUrl ? (
            <button
              type="button"
              onClick={() => setShowPdf((v) => !v)}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${showPdf ? "bg-indigo-600 text-white hover:bg-indigo-700" : "bg-gray-800 text-gray-300 hover:bg-gray-700 hover:text-white border border-gray-700"}`}
            >
              <FileText size={13} /> {showPdf ? "关闭预览" : "预览原文"}
            </button>
          ) : (
            <span
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs text-gray-600 border border-gray-800 cursor-default"
              title="文件未找到"
            >
              <FileText size={13} /> 原文仅支持下载
            </span>
          )}
          {isAdmin && downloadUrl && (
            <button
              type="button"
              onClick={handleDownload}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs bg-gray-800 text-gray-400 hover:text-white hover:bg-gray-700 border border-gray-700 transition-colors"
            >
              <Download size={13} /> 下载原文
            </button>
          )}
        </div>
      </div>
      {doc.refs.length > 0 && (
        <div
          className={showPdf ? "px-6 py-4 border-b border-gray-800" : "mb-8"}
        >
          <div className="text-xs text-gray-500 uppercase tracking-wider mb-2">
            引用文件
          </div>
          <div className="flex flex-wrap gap-2">
            {doc.refs.map((ref) => (
              <a
                key={ref}
                href={`/library/${ref}`}
                className="px-3 py-1 bg-gray-900 border border-gray-700 rounded-md text-sm font-mono text-indigo-400 hover:border-indigo-500 transition-colors"
              >
                {ref}
              </a>
            ))}
          </div>
        </div>
      )}
      <div className={showPdf ? "px-6 pt-3" : "mt-2"}>
        <div className="flex items-center gap-1 border-b border-gray-800 mb-4">
          {(
            [
              ["sections", `章节目录 (${doc.sections.length})`],
              ["drawings", "工程图纸"],
              ["reprocess", "重新处理"],
            ] as const
          ).map(([tab, label]) => (
            <button
              key={tab}
              type="button"
              onClick={() =>
                setActiveTab(tab as "sections" | "drawings" | "reprocess")
              }
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors -mb-px ${activeTab === tab ? "border-indigo-500 text-white" : "border-transparent text-gray-500 hover:text-gray-300"}`}
            >
              {label}
            </button>
          ))}
        </div>
        {activeTab === "sections" && (
          <DocSectionList
            visibleSections={visibleSections}
            sectionSearch={sectionSearch}
            setSectionSearch={setSectionSearch}
            expandedChunk={expandedChunk}
            loadingChunk={loadingChunk}
            activeChunk={activeChunk}
            sectionContent={sectionContent}
            sectionRowRefs={sectionRowRefs}
            onNavigate={onNavigate}
            onToggleExpand={onToggleExpand}
            onToggleFavorite={onToggleFavorite}
            getFavoriteId={getFavoriteId}
          />
        )}
        {activeTab === "drawings" && (
          <DrawingsTab docId={docId} targetImageId={targetImageId} />
        )}
        {activeTab === "reprocess" && (
          <ReprocessPanel docId={docId} onComplete={refresh} />
        )}
      </div>
    </div>
  );
}
