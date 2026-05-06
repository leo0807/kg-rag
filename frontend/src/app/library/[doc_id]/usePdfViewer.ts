"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  clamp, DEFAULT_SCALE, MIN_SCALE, MAX_SCALE,
  resolveRectFromBBox, resolveRectFromPageTextOrAnnotations,
  type PdfDocumentProxy, type HighlightRect,
} from "./pdfUtils";

interface Props {
  pdfUrl: string;
  anchorPage?: number;
  anchorBBox?: [number, number, number, number] | number[] | null;
  activeSectionNumber?: string;
  activeSectionTitle?: string;
  activeSectionLabel?: string;
  onManualPageChange?: (pageIndex: number) => void;
}

export function usePdfViewer({
  pdfUrl, anchorPage, anchorBBox,
  activeSectionNumber, activeSectionTitle, activeSectionLabel,
  onManualPageChange,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const scrollContainerRef = useRef<HTMLDivElement | null>(null);
  const highlightRef = useRef<HTMLDivElement | null>(null);
  const pdfDocRef = useRef<PdfDocumentProxy | null>(null);
  const renderTaskRef = useRef<{ cancel?: () => void } | null>(null);
  const latestRenderedPageRef = useRef<number | null>(null);
  const anchorPageRef = useRef<number | undefined>(anchorPage);
  const autoFitPendingRef = useRef(true);
  const followSectionTargetRef = useRef(true);
  const pageChangeScrollKeyRef = useRef<string | null>(null);
  const highlightScrollKeyRef = useRef<string | null>(null);

  const [previewError, setPreviewError] = useState<string | null>(null);
  const [docLoading, setDocLoading] = useState(true);
  const [pageRendering, setPageRendering] = useState(false);
  const [numPages, setNumPages] = useState(0);
  const [currentPage, setCurrentPage] = useState(anchorPage !== undefined ? anchorPage + 1 : 1);
  const [scale, setScale] = useState(DEFAULT_SCALE);
  const [pageSize, setPageSize] = useState({ width: 0, height: 0 });
  const [pageInput, setPageInput] = useState(String(anchorPage !== undefined ? anchorPage + 1 : 1));
  const [resolvedHighlightRect, setResolvedHighlightRect] = useState<HighlightRect | null>(null);
  const [renderedPageNumber, setRenderedPageNumber] = useState(0);
  const [fitScaleReady, setFitScaleReady] = useState(false);

  const isChecking = docLoading || !fitScaleReady || pageRendering || renderedPageNumber !== currentPage;
  const targetKey = useMemo(
    () => [anchorPage ?? "none", activeSectionNumber ?? "", activeSectionTitle ?? "", activeSectionLabel ?? ""].join(":"),
    [activeSectionLabel, activeSectionNumber, activeSectionTitle, anchorPage],
  );

  useEffect(() => { followSectionTargetRef.current = Boolean(activeSectionLabel); }, [activeSectionLabel]);

  useEffect(() => {
    anchorPageRef.current = anchorPage;
    if (anchorPage === undefined) return;
    const nextPage = anchorPage + 1;
    setCurrentPage((prev) => (prev === nextPage ? prev : nextPage));
    setPageInput(String(nextPage));
  }, [anchorPage]);

  useEffect(() => {
    if (!scrollContainerRef.current) return;
    const nextKey = `${currentPage}:${targetKey}`;
    if (pageChangeScrollKeyRef.current === nextKey) return;
    pageChangeScrollKeyRef.current = nextKey;
    scrollContainerRef.current.scrollTo({ top: 0, left: 0, behavior: "auto" });
    highlightScrollKeyRef.current = null;
    setResolvedHighlightRect(null);
  }, [currentPage, targetKey]);

  useEffect(() => {
    let cancelled = false;
    async function loadPdf() {
      setPreviewError(null); setDocLoading(true); setFitScaleReady(false);
      autoFitPendingRef.current = true; setRenderedPageNumber(0);
      setPageSize({ width: 0, height: 0 }); setResolvedHighlightRect(null);
      try {
        const pdfjs = await import("pdfjs-dist/build/pdf.mjs");
        pdfjs.GlobalWorkerOptions.workerSrc = new URL("pdfjs-dist/build/pdf.worker.min.mjs", import.meta.url).toString();
        pdfDocRef.current?.cleanup?.();
        await pdfDocRef.current?.destroy?.();
        pdfDocRef.current = null;
        const pdfDoc = (await pdfjs.getDocument({ url: pdfUrl, cMapPacked: true }).promise) as PdfDocumentProxy;
        if (cancelled) { await pdfDoc.destroy?.(); return; }
        pdfDocRef.current = pdfDoc;
        setNumPages(pdfDoc.numPages);
        const initialPage = Math.min(Math.max(anchorPageRef.current !== undefined ? anchorPageRef.current + 1 : 1, 1), pdfDoc.numPages);
        latestRenderedPageRef.current = null;
        setCurrentPage(initialPage);
        setPageInput(String(initialPage));
      } catch (error) {
        if (!cancelled) setPreviewError(error instanceof Error ? `PDF 预览加载失败：${error.message}` : "PDF 预览加载失败，请稍后重试。");
      } finally {
        if (!cancelled) setDocLoading(false);
      }
    }
    void loadPdf();
    return () => { cancelled = true; renderTaskRef.current?.cancel?.(); };
  }, [pdfUrl]);

  useEffect(() => {
    let cancelled = false;
    async function prepareFitScale() {
      const pdfDoc = pdfDocRef.current, container = scrollContainerRef.current;
      if (!pdfDoc || !container) return;
      if (!autoFitPendingRef.current) { setFitScaleReady(true); return; }
      if (numPages <= 0 || pdfDoc.numPages <= 0) return;
      const pageNumber = Math.min(Math.max(currentPage, 1), pdfDoc.numPages);
      if (!Number.isFinite(pageNumber) || pageNumber < 1) return;
      const page = await pdfDoc.getPage(pageNumber);
      const baseViewport = page.getViewport({ scale: 1 });
      const containerWidth = container.clientWidth;
      if (!containerWidth || !baseViewport.width) { if (!cancelled) setFitScaleReady(true); return; }
      const usableWidth = Math.max(containerWidth - 48, 240);
      const nextScale = clamp(usableWidth / baseViewport.width, MIN_SCALE, MAX_SCALE);
      if (cancelled) return;
      autoFitPendingRef.current = false;
      setScale((prev) => (Math.abs(prev - nextScale) < 0.01 ? prev : nextScale));
      setFitScaleReady(true);
    }
    void prepareFitScale();
    return () => { cancelled = true; };
  }, [currentPage, numPages]);

  useEffect(() => {
    let cancelled = false;
    async function renderPage() {
      const pdfDoc = pdfDocRef.current, canvas = canvasRef.current;
      if (!pdfDoc || !canvas || previewError || !fitScaleReady) return;
      if (currentPage < 1 || currentPage > pdfDoc.numPages) return;
      setPageRendering(true);
      setRenderedPageNumber((prev) => (prev === currentPage ? 0 : prev));
      try {
        renderTaskRef.current?.cancel?.();
        const page = await pdfDoc.getPage(currentPage);
        const viewport = page.getViewport({ scale });
        const context = canvas.getContext("2d");
        if (!context) throw new Error("无法初始化 Canvas 上下文");
        canvas.width = viewport.width; canvas.height = viewport.height;
        canvas.style.width = `${viewport.width}px`; canvas.style.height = `${viewport.height}px`;
        setPageSize({ width: viewport.width, height: viewport.height });
        const renderTask = page.render({ canvasContext: context, viewport });
        renderTaskRef.current = renderTask;
        await renderTask.promise;
        if (!cancelled) { latestRenderedPageRef.current = currentPage; setRenderedPageNumber(currentPage); setPageInput(String(currentPage)); }
      } catch (error) {
        if (!cancelled) {
          const message = error instanceof Error && error.name === "RenderingCancelledException" ? null : error instanceof Error ? `页面渲染失败：${error.message}` : "页面渲染失败，请稍后重试。";
          if (message) setPreviewError(message);
        }
      } finally { if (!cancelled) setPageRendering(false); }
    }
    void renderPage();
    return () => { cancelled = true; renderTaskRef.current?.cancel?.(); };
  }, [currentPage, fitScaleReady, previewError, scale]);

  useEffect(() => {
    return () => { pdfDocRef.current?.cleanup?.(); void pdfDocRef.current?.destroy?.(); pdfDocRef.current = null; };
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function resolveActiveTargetRect() {
      const pdfDoc = pdfDocRef.current;
      if (!pdfDoc || previewError || !followSectionTargetRef.current || !activeSectionLabel) { setResolvedHighlightRect(null); return; }
      const target = { number: activeSectionNumber, title: activeSectionTitle, label: activeSectionLabel };
      const preferredPage = typeof anchorPage === "number" && !Number.isNaN(anchorPage) ? anchorPage + 1 : currentPage;
      const pageOrder = [preferredPage, currentPage, ...Array.from({ length: pdfDoc.numPages }, (_, i) => i + 1)]
        .filter((p, i, arr) => p >= 1 && p <= pdfDoc.numPages && arr.indexOf(p) === i);
      let bestMatch: { pageNumber: number; rect: HighlightRect; score: number } | null = null;
      for (const pageNumber of pageOrder) {
        const page = await pdfDoc.getPage(pageNumber);
        const viewport = page.getViewport({ scale });
        const textMatch = await resolveRectFromPageTextOrAnnotations(page, viewport, target);
        const bboxRect = typeof anchorPage === "number" && pageNumber === anchorPage + 1 ? resolveRectFromBBox(anchorBBox, viewport.width, viewport.height, scale) : null;
        const textScore = textMatch.rect === null ? Number.NEGATIVE_INFINITY : textMatch.score - (textMatch.isTocLikePage ? 300 : 0);
        const bboxScore = bboxRect === null ? Number.NEGATIVE_INFINITY : 220 + (pageNumber === preferredPage ? 60 : 0);
        const candidate = textScore >= bboxScore && textMatch.rect ? { pageNumber, rect: textMatch.rect, score: textScore } : bboxRect ? { pageNumber, rect: bboxRect, score: bboxScore } : null;
        if (!candidate) continue;
        if (cancelled) return;
        if (!bestMatch || candidate.score > bestMatch.score) bestMatch = candidate;
      }
      if (bestMatch) {
        if (bestMatch.pageNumber !== currentPage) { setResolvedHighlightRect(null); setCurrentPage(bestMatch.pageNumber); setPageInput(String(bestMatch.pageNumber)); }
        else setResolvedHighlightRect(bestMatch.rect);
        return;
      }
      if (cancelled) return;
      setResolvedHighlightRect(null);
      if (typeof anchorPage === "number" && !Number.isNaN(anchorPage) && currentPage !== anchorPage + 1) { setCurrentPage(anchorPage + 1); setPageInput(String(anchorPage + 1)); }
    }
    void resolveActiveTargetRect();
    return () => { cancelled = true; };
  }, [activeSectionLabel, activeSectionNumber, activeSectionTitle, anchorBBox, anchorPage, currentPage, previewError, scale]);

  useEffect(() => {
    if (pageRendering || isChecking) return;
    if (!resolvedHighlightRect) { scrollContainerRef.current?.scrollTo({ top: 0, left: 0, behavior: "smooth" }); return; }
    if (!highlightRef.current) return;
    const nextKey = [currentPage, activeSectionLabel ?? "", Math.round(resolvedHighlightRect.left), Math.round(resolvedHighlightRect.top), Math.round(resolvedHighlightRect.width), Math.round(resolvedHighlightRect.height)].join(":");
    if (highlightScrollKeyRef.current === nextKey) return;
    highlightScrollKeyRef.current = nextKey;
    const frame = window.requestAnimationFrame(() => { highlightRef.current?.scrollIntoView({ block: "center", inline: "center", behavior: "smooth" }); });
    return () => window.cancelAnimationFrame(frame);
  }, [activeSectionLabel, currentPage, isChecking, pageRendering, resolvedHighlightRect]);

  function changePage(nextPage: number) {
    if (numPages <= 0) return;
    const clamped = Math.min(Math.max(nextPage, 1), numPages);
    if (clamped === currentPage) { setPageInput(String(clamped)); return; }
    followSectionTargetRef.current = false;
    setResolvedHighlightRect(null);
    highlightScrollKeyRef.current = null;
    setCurrentPage(clamped);
    setPageInput(String(clamped));
    onManualPageChange?.(clamped - 1);
  }

  function submitPageInput() {
    const parsed = parseInt(pageInput, 10);
    if (Number.isNaN(parsed)) { setPageInput(String(currentPage)); return; }
    changePage(parsed);
  }

  return {
    canvasRef, scrollContainerRef, highlightRef,
    followSectionTargetRef,
    previewError, docLoading, pageRendering, isChecking,
    numPages, currentPage, scale, setScale, pageSize,
    pageInput, setPageInput, resolvedHighlightRect,
    autoFitPendingRef, setFitScaleReady,
    changePage, submitPageInput,
  };
}
