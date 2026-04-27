"use client";

import { AlertTriangle, ChevronLeft, ChevronRight, Download, FileText, Loader2, X } from "lucide-react";
import { MIN_SCALE, MAX_SCALE } from "./pdfUtils";
import { usePdfViewer } from "./usePdfViewer";

interface Props {
  docId: string;
  pdfUrl: string;
  watermarkUrl: string;
  canDownload: boolean;
  anchorPage?: number;
  anchorBBox?: [number, number, number, number] | number[] | null;
  activeSectionNumber?: string;
  activeSectionTitle?: string;
  activeSectionLabel?: string;
  onManualPageChange?: (pageIndex: number) => void;
  onDownload: () => void;
  onClose: () => void;
}

export default function PdfPanel({
  docId, pdfUrl, watermarkUrl, canDownload,
  anchorPage, anchorBBox, activeSectionNumber, activeSectionTitle, activeSectionLabel,
  onManualPageChange, onDownload, onClose,
}: Props) {
  const {
    canvasRef, scrollContainerRef, highlightRef, followSectionTargetRef,
    previewError, isChecking, numPages, currentPage, scale, setScale, pageSize,
    pageInput, setPageInput, resolvedHighlightRect,
    autoFitPendingRef, setFitScaleReady,
    changePage, submitPageInput,
  } = usePdfViewer({ pdfUrl, anchorPage, anchorBBox, activeSectionNumber, activeSectionTitle, activeSectionLabel, onManualPageChange });

  return (
    <div className="flex flex-col border-l border-gray-800 bg-gray-900" style={{ width: "58%" }}>
      <div className="shrink-0 flex items-center gap-3 px-4 py-2.5 border-b border-gray-800 bg-gray-950">
        <FileText size={14} className="text-gray-500 shrink-0" />
        <div className="min-w-0 flex-1">
          <div className="text-xs text-gray-400 truncate font-mono">{docId} — 原文预览</div>
          {activeSectionLabel && followSectionTargetRef.current && (
            <div className="text-[11px] text-indigo-300 truncate mt-0.5">当前章节：{activeSectionLabel}</div>
          )}
        </div>

        <div className="flex items-center gap-1.5 rounded-lg border border-gray-800 bg-gray-900 px-2 py-1">
          <button type="button" onClick={() => changePage(currentPage - 1)} disabled={currentPage <= 1}
            className="rounded p-1 text-gray-400 hover:bg-gray-800 hover:text-white disabled:opacity-40 disabled:hover:bg-transparent" title="上一页">
            <ChevronLeft size={14} />
          </button>
          <input value={pageInput} onChange={(e) => setPageInput(e.target.value)} onBlur={submitPageInput}
            onKeyDown={(e) => { if (e.key === "Enter") submitPageInput(); }}
            className="w-12 rounded bg-gray-950 px-1.5 py-0.5 text-center text-xs text-white outline-none" />
          <span className="text-xs text-gray-500">/ {numPages || "—"}</span>
          <button type="button" onClick={() => changePage(currentPage + 1)} disabled={numPages > 0 ? currentPage >= numPages : true}
            className="rounded p-1 text-gray-400 hover:bg-gray-800 hover:text-white disabled:opacity-40 disabled:hover:bg-transparent" title="下一页">
            <ChevronRight size={14} />
          </button>
        </div>

        <div className="flex items-center gap-1.5 rounded-lg border border-gray-800 bg-gray-900 px-2 py-1">
          <button type="button" onClick={() => { autoFitPendingRef.current = false; setFitScaleReady(true); setScale((prev) => Math.max(MIN_SCALE, prev - 0.1)); }}
            className="rounded px-2 py-0.5 text-sm text-gray-400 hover:bg-gray-800 hover:text-white" title="缩小">-</button>
          <span className="w-14 text-center text-xs text-gray-300">{Math.round(scale * 100)}%</span>
          <button type="button" onClick={() => { autoFitPendingRef.current = false; setFitScaleReady(true); setScale((prev) => Math.min(MAX_SCALE, prev + 0.1)); }}
            className="rounded px-2 py-0.5 text-sm text-gray-400 hover:bg-gray-800 hover:text-white" title="放大">+</button>
        </div>

        {canDownload && (
          <button type="button" onClick={onDownload} className="p-1.5 rounded text-gray-500 hover:text-white hover:bg-gray-800 transition-colors" title="下载原文">
            <Download size={13} />
          </button>
        )}
        <button type="button" onClick={onClose} className="p-1.5 rounded text-gray-500 hover:text-white hover:bg-gray-800 transition-colors" title="关闭预览">
          <X size={14} />
        </button>
      </div>

      <div ref={scrollContainerRef} className="relative flex-1 overflow-auto bg-[#111827]">
        {isChecking && !previewError && (
          <div className="absolute inset-0 flex items-center justify-center bg-gray-900/80 z-10">
            <Loader2 size={24} className="animate-spin text-gray-500" />
          </div>
        )}
        {previewError ? (
          <div className="flex flex-col items-center justify-center h-full gap-4 px-8 text-center">
            <AlertTriangle size={32} className="text-amber-500 shrink-0" />
            <div className="text-sm text-gray-300 leading-relaxed">{previewError}</div>
            {canDownload && (
              <button type="button" onClick={onDownload} className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg transition-colors">
                <Download size={14} /> 下载原文
              </button>
            )}
          </div>
        ) : (
          <div className="min-h-full flex items-start justify-center p-6">
            <div className="relative shrink-0 rounded-sm shadow-2xl" style={{ width: pageSize.width || undefined, height: pageSize.height || undefined }}>
              <canvas ref={canvasRef} className="block bg-white" />
              {resolvedHighlightRect && (
                <div ref={highlightRef} className="absolute border-2 border-amber-400 bg-amber-300/20 shadow-[0_0_0_9999px_rgba(15,23,42,0.08)]" style={resolvedHighlightRect} />
              )}
              {watermarkUrl && (
                <div className="absolute inset-0 pointer-events-none" style={{ backgroundImage: watermarkUrl, backgroundRepeat: "repeat", backgroundSize: "280px 140px" }} />
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
