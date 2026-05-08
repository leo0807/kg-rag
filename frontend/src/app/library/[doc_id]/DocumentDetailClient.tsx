"use client";

import { Loader2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { DocumentDetailPanel } from "./DocumentDetailPanel";
import { sortSections } from "./docDetailUtils";
import PdfPanel from "./PdfPanel";
import { useDocDetail } from "./useDocDetail";
import { useDocumentDetailViewport } from "./useDocumentDetailViewport";

export default function DocumentDetailClient({ docId }: { docId: string }) {
  const {
    doc,
    pdfUrl,
    downloadUrl,
    isAdmin,
    showPdf,
    setShowPdf,
    anchorPage,
    watermarkUrl,
    activeTab,
    setActiveTab,
    expandedChunk,
    activeChunk,
    setActiveChunk,
    sectionContent,
    loadingChunk,
    sectionSearch,
    setSectionSearch,
    sectionRequestsRef,
    sectionContentRef,
    refresh,
    handleDownload,
    ensureSectionContent,
    toggleSectionExpand,
    handleSectionNavigate,
    toggleSectionFavorite,
    clearActiveSectionSelection,
    getFavoriteId,
  } = useDocDetail(docId);

  const sortedSections = useMemo(
    () => sortSections(doc?.sections ?? []),
    [doc?.sections],
  );
  const activeSection = useMemo(() => {
    if (!activeChunk) return undefined;
    return sortedSections.find((s) => s.chunk_id === activeChunk);
  }, [activeChunk, sortedSections]);
  const activeSectionLabel = useMemo(
    () =>
      activeSection
        ? `§${activeSection.number} ${activeSection.title}`
        : undefined,
    [activeSection],
  );
  const visibleSections = useMemo(
    () =>
      sectionSearch
        ? sortedSections.filter(
            (s) =>
              s.title.toLowerCase().includes(sectionSearch.toLowerCase()) ||
              s.number.includes(sectionSearch),
          )
        : sortedSections,
    [sectionSearch, sortedSections],
  );

  const { scrollContainerRef, sectionRowRefs } = useDocumentDetailViewport({
    doc,
    activeTab,
    visibleSections,
    expandedChunk,
    ensureSectionContent,
    sectionRequestsRef,
    sectionContentRef,
    pdfUrl,
    setActiveTab,
  });

  const [targetImageId] = useState(() =>
    typeof window !== "undefined"
      ? (new URLSearchParams(window.location.search).get("image_id") ??
        undefined)
      : undefined,
  );

  useEffect(() => {
    if (
      !doc?.sections?.length ||
      anchorPage === undefined ||
      Number.isNaN(anchorPage)
    )
      return;
    const byPage = [...doc.sections]
      .filter(
        (s): s is (typeof doc.sections)[number] & { page_idx: number } =>
          typeof s.page_idx === "number",
      )
      .sort((a, b) => a.page_idx - b.page_idx);
    if (!byPage.length) return;
    const samePageSections = byPage.filter((s) => s.page_idx === anchorPage);
    const current =
      samePageSections[0] ??
      byPage.reduce<(typeof byPage)[number] | null>((best, s) => {
        if (s.page_idx > anchorPage) return best;
        return !best ? s : s.page_idx >= (best.page_idx ?? -1) ? s : best;
      }, null);
    if (current) {
      setActiveChunk((prev) =>
        prev === current.chunk_id ? prev : current.chunk_id,
      );
    }
  }, [anchorPage, doc?.sections, setActiveChunk]);

  if (!doc) {
    return (
      <div className="flex items-center justify-center h-full text-gray-500 text-sm gap-2">
        <Loader2 size={16} className="animate-spin" /> 加载中...
      </div>
    );
  }

  const leftPanel = (
    <DocumentDetailPanel
      doc={doc}
      docId={docId}
      scrollContainerRef={scrollContainerRef}
      pdfUrl={pdfUrl}
      downloadUrl={downloadUrl}
      isAdmin={isAdmin}
      showPdf={showPdf}
      activeTab={activeTab}
      expandedChunk={expandedChunk}
      activeChunk={activeChunk}
      sectionContent={sectionContent}
      loadingChunk={loadingChunk}
      sectionSearch={sectionSearch}
      visibleSections={visibleSections}
      sectionRowRefs={sectionRowRefs}
      targetImageId={targetImageId}
      refresh={refresh}
      handleDownload={handleDownload}
      setShowPdf={setShowPdf}
      setActiveTab={setActiveTab}
      setSectionSearch={setSectionSearch}
      onNavigate={handleSectionNavigate}
      onToggleExpand={toggleSectionExpand}
      onToggleFavorite={toggleSectionFavorite}
      getFavoriteId={getFavoriteId}
    />
  );

  if (showPdf && pdfUrl) {
    return (
      <div className="flex h-full overflow-hidden">
        <div className="flex flex-col overflow-hidden" style={{ width: "42%" }}>
          {leftPanel}
        </div>
        <PdfPanel
          docId={doc.doc_id}
          pdfUrl={pdfUrl}
          watermarkUrl={watermarkUrl}
          canDownload={isAdmin && Boolean(downloadUrl)}
          anchorPage={anchorPage}
          anchorBBox={
            activeSection && typeof activeSection.page_idx === "number"
              ? (activeSection.bbox ?? undefined)
              : undefined
          }
          activeSectionNumber={activeSection?.number}
          activeSectionTitle={activeSection?.title}
          activeSectionLabel={activeSectionLabel}
          onManualPageChange={clearActiveSectionSelection}
          onDownload={handleDownload}
          onClose={() => setShowPdf(false)}
        />
      </div>
    );
  }

  return leftPanel;
}
