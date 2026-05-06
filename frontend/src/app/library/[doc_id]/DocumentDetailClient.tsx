"use client";

import { ArrowLeft, Download, FileText, Loader2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { DrawingsTab } from "./DrawingsTab";
import { DocSectionList } from "./DocSectionList";
import PdfPanel from "./PdfPanel";
import { ReprocessPanel } from "./ReprocessPanel";
import { useDocDetail } from "./useDocDetail";

type IdleDeadlineLike = { didTimeout: boolean; timeRemaining: () => number };
type IdleWindow = Window & {
  requestIdleCallback?: (cb: (dl: IdleDeadlineLike) => void, opts?: { timeout: number }) => number;
  cancelIdleCallback?: (h: number) => void;
};

export default function DocumentDetailClient({ docId }: { docId: string }) {
  const {
    doc, pdfUrl, downloadUrl, isAdmin, showPdf, setShowPdf, anchorPage,
    watermarkUrl, activeTab, setActiveTab, expandedChunk, activeChunk, sectionContent,
    loadingChunk, sectionSearch, setSectionSearch, activeSection, activeSectionLabel,
    visibleSections, sectionRequestsRef, sectionContentRef,
    refresh, handleDownload, ensureSectionContent, toggleSectionExpand,
    handleSectionNavigate, toggleSectionFavorite, clearActiveSectionSelection, getFavoriteId,
  } = useDocDetail(docId);

  const [targetImageId] = useState(() =>
    typeof window !== "undefined"
      ? (new URLSearchParams(window.location.search).get("image_id") ?? undefined)
      : undefined,
  );
  const [visibleSectionIds, setVisibleSectionIds] = useState<string[]>([]);
  const scrollContainerRef = useRef<HTMLDivElement | null>(null);
  const sectionRowRefs = useRef(new Map<string, HTMLDivElement>());
  const highlightedRef = useRef(false);
  const visibleSectionIdsRef = useRef(new Set<string>());
  const idlePrefetchHandleRef = useRef<number | null>(null);
  const prefetchingChunkRef = useRef<string | null>(null);

  // Intersection observer for section visibility tracking
  useEffect(() => {
    if (!doc) return;
    if (activeTab !== "sections") {
      visibleSectionIdsRef.current.clear();
      setVisibleSectionIds([]);
      return;
    }
    const root = scrollContainerRef.current;
    if (!root) return;
    const observer = new IntersectionObserver(
      (entries) => {
        let changed = false;
        const next = new Set(visibleSectionIdsRef.current);
        for (const entry of entries) {
          const chunkId = (entry.target as HTMLElement).dataset.chunkId;
          if (!chunkId) continue;
          if (entry.isIntersecting) { if (!next.has(chunkId)) { next.add(chunkId); changed = true; } }
          else if (next.delete(chunkId)) { changed = true; }
        }
        if (!changed) return;
        visibleSectionIdsRef.current = next;
        const ordered = visibleSections.filter((s) => next.has(s.chunk_id)).map((s) => s.chunk_id);
        setVisibleSectionIds((prev) =>
          prev.length === ordered.length && prev.every((v, i) => v === ordered[i]) ? prev : ordered,
        );
      },
      { root, rootMargin: "140px 0px", threshold: 0.01 },
    );
    for (const section of visibleSections) {
      const node = sectionRowRefs.current.get(section.chunk_id);
      if (node) observer.observe(node);
    }
    return () => observer.disconnect();
  }, [activeTab, visibleSections, doc]);

  // Idle prefetch for visible sections
  useEffect(() => {
    if (!doc || activeTab !== "sections" || !visibleSectionIds.length) return;
    if (prefetchingChunkRef.current) return;
    const queue = visibleSections.filter(
      (s) => visibleSectionIds.includes(s.chunk_id) && !sectionContentRef.current[s.chunk_id]
        && !sectionRequestsRef.current.has(s.chunk_id) && s.chunk_id !== expandedChunk,
    );
    const next = queue[0];
    if (!next) return;
    let cancelled = false;
    const idleWindow = window as IdleWindow;
    const runPrefetch = async (deadline: IdleDeadlineLike) => {
      if (cancelled) return;
      if (!deadline.didTimeout && deadline.timeRemaining() < 8) { schedulePrefetch(); return; }
      prefetchingChunkRef.current = next.chunk_id;
      try { await ensureSectionContent(next, { background: true }); }
      finally { prefetchingChunkRef.current = null; idlePrefetchHandleRef.current = null; }
    };
    const schedulePrefetch = () => {
      if (cancelled || idlePrefetchHandleRef.current !== null) return;
      if (idleWindow.requestIdleCallback) {
        idlePrefetchHandleRef.current = idleWindow.requestIdleCallback(
          (dl) => { idlePrefetchHandleRef.current = null; void runPrefetch(dl); },
          { timeout: 1200 },
        );
      } else {
        idlePrefetchHandleRef.current = window.setTimeout(() => {
          idlePrefetchHandleRef.current = null;
          void runPrefetch({ didTimeout: true, timeRemaining: () => 0 });
        }, 180);
      }
    };
    schedulePrefetch();
    return () => {
      cancelled = true;
      if (idlePrefetchHandleRef.current !== null) {
        if (idleWindow.cancelIdleCallback) idleWindow.cancelIdleCallback(idlePrefetchHandleRef.current);
        else window.clearTimeout(idlePrefetchHandleRef.current);
        idlePrefetchHandleRef.current = null;
      }
    };
  }, [activeTab, ensureSectionContent, expandedChunk, visibleSectionIds, visibleSections, doc, sectionContentRef, sectionRequestsRef]);

  // Scroll to and highlight a section when navigated from graph (?section=chunk_id)
  useEffect(() => {
    if (!doc || !visibleSections.length || highlightedRef.current) return;
    const params = new URLSearchParams(window.location.search);
    const targetId = params.get("section");
    if (!targetId) return;
    const found = visibleSections.find(s => s.chunk_id === targetId);
    if (!found) return;
    // When PDF is set to open, wait for pdfUrl so the layout is stable before scrolling
    if (params.get("preview") === "true" && !pdfUrl) return;
    highlightedRef.current = true;
    setActiveTab("sections");
    let attempt = 0;
    let timerId: ReturnType<typeof setTimeout>;
    const tryScroll = () => {
      const el = document.getElementById(`section-${targetId}`);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
        el.style.transition = "background-color 0.4s";
        el.style.backgroundColor = "rgba(234,179,8,0.18)";
        setTimeout(() => { el.style.backgroundColor = ""; }, 3000);
      } else if (attempt < 20) {
        attempt++;
        timerId = setTimeout(tryScroll, 300);
      }
    };
    timerId = setTimeout(tryScroll, 300);
    return () => clearTimeout(timerId);
  }, [doc, visibleSections, pdfUrl]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!doc) {
    return (
      <div className="flex items-center justify-center h-full text-gray-500 text-sm gap-2">
        <Loader2 size={16} className="animate-spin" /> 加载中...
      </div>
    );
  }

  const docPanel = (
    <div
      ref={scrollContainerRef}
      className={`bg-gray-950 overflow-y-auto ${showPdf ? "flex-1 min-w-0" : "p-8 max-w-3xl min-h-screen"}`}
    >
      <div className={showPdf ? "px-6 pt-5 pb-4" : "mb-6"}>
        <a href="/library" className="inline-flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-300 transition-colors">
          <ArrowLeft size={14} /> 返回文档库
        </a>
      </div>

      <div className={showPdf ? "px-6 pb-4 border-b border-gray-800" : "mb-8"}>
        <div className="text-sm font-mono text-indigo-400 mb-1">{doc.doc_id} · 版本 {doc.version || "—"}</div>
        <h1 className="text-xl font-semibold text-white leading-snug">{doc.title || "未命名文档"}</h1>
        <div className="text-sm text-gray-500 mt-1">发布日期：{doc.issue_date || "—"}</div>
        <div className="flex items-center gap-2 mt-3">
          {pdfUrl ? (
            <button type="button" onClick={() => setShowPdf((v) => !v)}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${showPdf ? "bg-indigo-600 text-white hover:bg-indigo-700" : "bg-gray-800 text-gray-300 hover:bg-gray-700 hover:text-white border border-gray-700"}`}>
              <FileText size={13} /> {showPdf ? "关闭预览" : "预览原文"}
            </button>
          ) : (
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs text-gray-600 border border-gray-800 cursor-default" title="文件未找到">
              <FileText size={13} /> 原文仅支持下载
            </span>
          )}
          {isAdmin && downloadUrl && (
            <button type="button" onClick={handleDownload}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs bg-gray-800 text-gray-400 hover:text-white hover:bg-gray-700 border border-gray-700 transition-colors">
              <Download size={13} /> 下载原文
            </button>
          )}
        </div>
      </div>

      {doc.refs.length > 0 && (
        <div className={showPdf ? "px-6 py-4 border-b border-gray-800" : "mb-8"}>
          <div className="text-xs text-gray-500 uppercase tracking-wider mb-2">引用文件</div>
          <div className="flex flex-wrap gap-2">
            {doc.refs.map((ref) => (
              <a key={ref} href={`/library/${ref}`}
                className="px-3 py-1 bg-gray-900 border border-gray-700 rounded-md text-sm font-mono text-indigo-400 hover:border-indigo-500 transition-colors">
                {ref}
              </a>
            ))}
          </div>
        </div>
      )}

      <div className={showPdf ? "px-6 pt-3" : "mt-2"}>
        <div className="flex items-center gap-1 border-b border-gray-800 mb-4">
          {([ ["sections", `章节目录 (${doc.sections.length})`], ["drawings", "工程图纸"], ["reprocess", "重新处理"] ] as const).map(([tab, label]) => (
            <button key={tab} type="button" onClick={() => {
              setActiveTab(tab as "sections" | "drawings" | "reprocess");
              history.replaceState(null, "", tab === "sections"
                ? window.location.pathname + window.location.search
                : `${window.location.pathname}${window.location.search}#${tab}`);
            }}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors -mb-px ${activeTab === tab ? "border-indigo-500 text-white" : "border-transparent text-gray-500 hover:text-gray-300"}`}>
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
            onNavigate={handleSectionNavigate}
            onToggleExpand={toggleSectionExpand}
            onToggleFavorite={toggleSectionFavorite}
            getFavoriteId={getFavoriteId}
          />
        )}
        {activeTab === "drawings" && <DrawingsTab docId={docId} targetImageId={targetImageId} />}
        {activeTab === "reprocess" && <ReprocessPanel docId={docId} onComplete={refresh} />}
      </div>
    </div>
  );

  if (showPdf && pdfUrl) {
    return (
      <div className="flex h-full overflow-hidden">
        <div className="flex flex-col overflow-hidden" style={{ width: "42%" }}>{docPanel}</div>
        <PdfPanel
          docId={doc.doc_id} pdfUrl={pdfUrl} watermarkUrl={watermarkUrl}
          canDownload={isAdmin && Boolean(downloadUrl)} anchorPage={anchorPage}
          anchorBBox={activeSection && typeof activeSection.page_idx === "number" ? (activeSection.bbox ?? undefined) : undefined}
          activeSectionNumber={activeSection?.number} activeSectionTitle={activeSection?.title}
          activeSectionLabel={activeSectionLabel} onManualPageChange={clearActiveSectionSelection}
          onDownload={handleDownload} onClose={() => setShowPdf(false)}
        />
      </div>
    );
  }

  return docPanel;
}
