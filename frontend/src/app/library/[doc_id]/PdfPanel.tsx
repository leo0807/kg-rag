"use client";

import {
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  Download,
  FileText,
  Loader2,
  X,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

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

type PdfDocumentProxy = {
  numPages: number;
  getPage: (pageNumber: number) => Promise<PdfPageProxy>;
  destroy?: () => Promise<void> | void;
  cleanup?: () => void;
};

type PdfPageProxy = {
  getViewport: (args: { scale: number }) => {
    width: number;
    height: number;
    convertToViewportRectangle?: (rect: number[]) => number[];
  };
  getTextContent?: () => Promise<{
    items: Array<{
      str?: string;
      width?: number;
      height?: number;
      transform?: number[];
    }>;
  }>;
  getAnnotations?: () => Promise<
    Array<{
      rect?: number[];
      contents?: string;
      title?: string;
      fieldValue?: string;
      alternativeText?: string;
    }>
  >;
  render: (args: {
    canvasContext: CanvasRenderingContext2D;
    viewport: { width: number; height: number };
  }) => { promise: Promise<void>; cancel?: () => void };
  cleanup?: () => void;
};

const MIN_SCALE = 0.6;
const MAX_SCALE = 2.4;
const DEFAULT_SCALE = 1.35;

type HighlightRect = {
  left: number;
  top: number;
  width: number;
  height: number;
};

type ResolvedTargetMatch = {
  rect: HighlightRect | null;
  score: number;
  isTocLikePage: boolean;
};

type SectionTarget = {
  number?: string;
  title?: string;
  label?: string;
};

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

function normalizeHighlightRect(
  rect: HighlightRect,
  pageWidth: number,
  pageHeight: number,
): HighlightRect | null {
  if (pageWidth <= 0 || pageHeight <= 0) return null;
  if ([rect.left, rect.top, rect.width, rect.height].some(Number.isNaN)) {
    return null;
  }

  const left = clamp(rect.left, 0, pageWidth);
  const top = clamp(rect.top, 0, pageHeight);
  const right = clamp(rect.left + rect.width, 0, pageWidth);
  const bottom = clamp(rect.top + rect.height, 0, pageHeight);
  const width = right - left;
  const height = bottom - top;

  if (width <= 0 || height <= 0) return null;

  return {
    left,
    top,
    width: clamp(Math.max(12, width), 1, pageWidth - left),
    height: clamp(Math.max(10, height), 1, pageHeight - top),
  };
}

function scoreHighlightRect(
  rect: HighlightRect,
  pageWidth: number,
  pageHeight: number,
) {
  const overflowLeft = Math.max(0, -rect.left);
  const overflowTop = Math.max(0, -rect.top);
  const overflowRight = Math.max(0, rect.left + rect.width - pageWidth);
  const overflowBottom = Math.max(0, rect.top + rect.height - pageHeight);
  return overflowLeft + overflowTop + overflowRight + overflowBottom;
}

function normalizeMatchText(value: string | undefined | null) {
  return String(value ?? "")
    .toLowerCase()
    .replace(/[\s\u00a0.,;:!?'"()（）【】[\]{}<>《》、，。；：·•\-_/]+/g, "");
}

function padHighlightRect(
  rect: HighlightRect,
  pageWidth: number,
  pageHeight: number,
  padding = 10,
) {
  return normalizeHighlightRect(
    {
      left: rect.left - padding,
      top: rect.top - padding,
      width: rect.width + padding * 2,
      height: rect.height + padding * 2,
    },
    pageWidth,
    pageHeight,
  );
}

function unionHighlightRects(rects: HighlightRect[]): HighlightRect | null {
  if (rects.length === 0) return null;
  const left = Math.min(...rects.map((rect) => rect.left));
  const top = Math.min(...rects.map((rect) => rect.top));
  const right = Math.max(...rects.map((rect) => rect.left + rect.width));
  const bottom = Math.max(...rects.map((rect) => rect.top + rect.height));
  return {
    left,
    top,
    width: right - left,
    height: bottom - top,
  };
}

function resolveRectFromBBox(
  bbox: [number, number, number, number] | number[] | null | undefined,
  pageWidth: number,
  pageHeight: number,
  scale: number,
): HighlightRect | null {
  if (
    !Array.isArray(bbox) ||
    bbox.length < 4 ||
    pageWidth <= 0 ||
    pageHeight <= 0
  ) {
    return null;
  }

  const [x0, top, x1, bottom] = bbox.map((value) =>
    typeof value === "number" ? value : Number(value),
  );
  if ([x0, top, x1, bottom].some((value) => Number.isNaN(value))) return null;

  const unscaledPageHeight = pageHeight / scale;
  const rectWidth = Math.abs(x1 - x0) * scale;
  const rectHeight = Math.abs(bottom - top) * scale;

  const candidates: HighlightRect[] = [
    {
      left: Math.min(x0, x1) * scale,
      top: Math.min(top, bottom) * scale,
      width: rectWidth,
      height: rectHeight,
    },
  ];

  if (unscaledPageHeight > 0) {
    candidates.push({
      left: Math.min(x0, x1) * scale,
      top: (unscaledPageHeight - Math.max(top, bottom)) * scale,
      width: rectWidth,
      height: rectHeight,
    });
  }

  const bestCandidate = candidates
    .map((candidate) => ({
      score: scoreHighlightRect(candidate, pageWidth, pageHeight),
      rect: normalizeHighlightRect(candidate, pageWidth, pageHeight),
    }))
    .filter(
      (candidate): candidate is { score: number; rect: HighlightRect } =>
        candidate.rect !== null,
    )
    .sort((a, b) => a.score - b.score)[0];

  return bestCandidate?.rect ?? null;
}

function isLikelyTocPage(rows: string[]) {
  if (rows.length === 0) return false;
  const normalizedRows = rows.map((row) => row.trim()).filter(Boolean);
  const fullText = normalizedRows.join("\n");
  if (
    /(^|\n)\s*(目录|目\s*录|contents?|table\s+of\s+contents)\s*($|\n)/i.test(
      fullText,
    )
  ) {
    return true;
  }

  const dottedRows = normalizedRows.filter((row) =>
    /(\.{3,}|…{2,}|·{3,})/.test(row),
  ).length;
  const indexRows = normalizedRows.filter((row) =>
    /^\s*\d+(?:\.\d+)*\s+\S.+\d+\s*$/.test(row),
  ).length;

  return dottedRows >= 3 || indexRows >= 5;
}

function toViewportRect(
  rect: number[],
  viewport: {
    width: number;
    height: number;
    convertToViewportRectangle?: (rect: number[]) => number[];
  },
) {
  if (viewport.convertToViewportRectangle) {
    const [x0, y0, x1, y1] = viewport.convertToViewportRectangle(rect);
    return normalizeHighlightRect(
      {
        left: Math.min(x0, x1),
        top: Math.min(y0, y1),
        width: Math.abs(x1 - x0),
        height: Math.abs(y1 - y0),
      },
      viewport.width,
      viewport.height,
    );
  }

  return normalizeHighlightRect(
    {
      left: Math.min(rect[0], rect[2]),
      top: Math.min(rect[1], rect[3]),
      width: Math.abs(rect[2] - rect[0]),
      height: Math.abs(rect[3] - rect[1]),
    },
    viewport.width,
    viewport.height,
  );
}

async function resolveRectFromPageTextOrAnnotations(
  page: PdfPageProxy,
  viewport: {
    width: number;
    height: number;
    convertToViewportRectangle?: (rect: number[]) => number[];
  },
  target: SectionTarget,
): Promise<ResolvedTargetMatch> {
  const numberNorm = normalizeMatchText(target.number);
  const titleNorm = normalizeMatchText(target.title);
  const labelNorm = normalizeMatchText(target.label);
  const titlePrefix = titleNorm.slice(0, Math.min(titleNorm.length, 10));
  const needles = [
    labelNorm,
    `${numberNorm}${titleNorm}`,
    titleNorm,
    numberNorm,
  ].filter(Boolean);
  if (needles.length === 0) {
    return {
      rect: null,
      score: Number.NEGATIVE_INFINITY,
      isTocLikePage: false,
    };
  }

  const candidates: Array<{ score: number; rect: HighlightRect }> = [];
  let isTocLikePage = false;

  if (page.getTextContent) {
    const textContent = await page.getTextContent();
    const groups = new Map<
      number,
      Array<{ str: string; x: number; rect: HighlightRect }>
    >();

    for (const item of textContent.items ?? []) {
      const str = String(item.str ?? "").trim();
      const transform = item.transform ?? [];
      if (!str || transform.length < 6) continue;

      const x = transform[4];
      const y = transform[5];
      const width = Math.max(Number(item.width ?? 0), 2);
      const height = Math.max(
        Math.abs(Number(item.height ?? 0)),
        Math.abs(transform[3] ?? 0),
        8,
      );
      const rect = toViewportRect([x, y, x + width, y + height], viewport);
      if (!rect) continue;

      const key = Math.round(y / 2) * 2;
      const row = groups.get(key) ?? [];
      row.push({ str, x, rect });
      groups.set(key, row);
    }

    const orderedRows = [...groups.entries()]
      .sort((a, b) => b[0] - a[0])
      .map(([, row]) => {
        const ordered = [...row].sort((a, b) => a.x - b.x);
        return {
          ordered,
          joined: ordered.map((item) => item.str).join(" "),
        };
      });

    isTocLikePage = isLikelyTocPage(orderedRows.map((row) => row.joined));

    for (const row of orderedRows) {
      const joinedNorm = normalizeMatchText(row.joined);
      let score = 0;

      if (labelNorm && joinedNorm.includes(labelNorm)) score += 140;
      if (titleNorm && joinedNorm.includes(titleNorm)) score += 120;
      if (numberNorm && joinedNorm.includes(numberNorm)) score += 40;
      if (
        numberNorm &&
        titlePrefix &&
        joinedNorm.includes(numberNorm) &&
        joinedNorm.includes(titlePrefix)
      ) {
        score += 80;
      }

      if (score <= 0) continue;

      const rect = unionHighlightRects(row.ordered.map((item) => item.rect));
      const padded = rect
        ? padHighlightRect(rect, viewport.width, viewport.height, 8)
        : null;
      if (padded) {
        candidates.push({ score, rect: padded });
      }
    }
  }

  if (page.getAnnotations) {
    const annotations = await page.getAnnotations();
    for (const annotation of annotations ?? []) {
      const text = normalizeMatchText(
        [
          annotation.contents,
          annotation.title,
          annotation.fieldValue,
          annotation.alternativeText,
        ]
          .filter(Boolean)
          .join(" "),
      );
      if (!text || !annotation.rect || annotation.rect.length < 4) continue;

      let score = 0;
      if (labelNorm && text.includes(labelNorm)) score += 150;
      if (titleNorm && text.includes(titleNorm)) score += 130;
      if (numberNorm && text.includes(numberNorm)) score += 50;
      if (score <= 0) continue;

      const rect = toViewportRect(annotation.rect, viewport);
      const padded = rect
        ? padHighlightRect(rect, viewport.width, viewport.height, 8)
        : null;
      if (padded) {
        candidates.push({ score, rect: padded });
      }
    }
  }

  candidates.sort((a, b) => b.score - a.score);
  return {
    rect: candidates[0]?.rect ?? null,
    score: candidates[0]?.score ?? Number.NEGATIVE_INFINITY,
    isTocLikePage,
  };
}

export default function PdfPanel({
  docId,
  pdfUrl,
  watermarkUrl,
  canDownload,
  anchorPage,
  anchorBBox,
  activeSectionNumber,
  activeSectionTitle,
  activeSectionLabel,
  onManualPageChange,
  onDownload,
  onClose,
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
  const [currentPage, setCurrentPage] = useState(
    anchorPage !== undefined ? anchorPage + 1 : 1,
  );
  const [scale, setScale] = useState(DEFAULT_SCALE);
  const [pageSize, setPageSize] = useState({ width: 0, height: 0 });
  const [pageInput, setPageInput] = useState(
    String(anchorPage !== undefined ? anchorPage + 1 : 1),
  );
  const [resolvedHighlightRect, setResolvedHighlightRect] =
    useState<HighlightRect | null>(null);
  const [renderedPageNumber, setRenderedPageNumber] = useState(0);
  const [fitScaleReady, setFitScaleReady] = useState(false);

  const isChecking =
    docLoading ||
    !fitScaleReady ||
    pageRendering ||
    renderedPageNumber !== currentPage;
  const targetKey = useMemo(
    () =>
      [
        anchorPage ?? "none",
        activeSectionNumber ?? "",
        activeSectionTitle ?? "",
        activeSectionLabel ?? "",
      ].join(":"),
    [activeSectionLabel, activeSectionNumber, activeSectionTitle, anchorPage],
  );

  useEffect(() => {
    followSectionTargetRef.current = Boolean(activeSectionLabel);
  }, [activeSectionLabel]);

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
      setPreviewError(null);
      setDocLoading(true);
      setFitScaleReady(false);
      autoFitPendingRef.current = true;
      setRenderedPageNumber(0);
      setPageSize({ width: 0, height: 0 });
      setResolvedHighlightRect(null);

      try {
        const pdfjs = await import("pdfjs-dist/build/pdf.mjs");
        pdfjs.GlobalWorkerOptions.workerSrc = new URL(
          "pdfjs-dist/build/pdf.worker.min.mjs",
          import.meta.url,
        ).toString();

        pdfDocRef.current?.cleanup?.();
        await pdfDocRef.current?.destroy?.();
        pdfDocRef.current = null;

        const loadingTask = pdfjs.getDocument({
          url: pdfUrl,
          cMapPacked: true,
        });
        const pdfDoc = (await loadingTask.promise) as PdfDocumentProxy;
        if (cancelled) {
          await pdfDoc.destroy?.();
          return;
        }

        pdfDocRef.current = pdfDoc;
        setNumPages(pdfDoc.numPages);
        const initialPage = Math.min(
          Math.max(
            anchorPageRef.current !== undefined ? anchorPageRef.current + 1 : 1,
            1,
          ),
          pdfDoc.numPages,
        );
        latestRenderedPageRef.current = null;
        setCurrentPage(initialPage);
        setPageInput(String(initialPage));
      } catch (error) {
        if (!cancelled) {
          setPreviewError(
            error instanceof Error
              ? `PDF 预览加载失败：${error.message}`
              : "PDF 预览加载失败，请稍后重试。",
          );
        }
      } finally {
        if (!cancelled) {
          setDocLoading(false);
        }
      }
    }

    void loadPdf();
    return () => {
      cancelled = true;
      renderTaskRef.current?.cancel?.();
    };
  }, [pdfUrl]);

  useEffect(() => {
    let cancelled = false;

    async function prepareFitScale() {
      const pdfDoc = pdfDocRef.current;
      const container = scrollContainerRef.current;
      if (!pdfDoc || !container) return;
      if (!autoFitPendingRef.current) {
        setFitScaleReady(true);
        return;
      }
      if (numPages <= 0) return;

      const pageNumber = Math.min(Math.max(currentPage, 1), pdfDoc.numPages);
      const page = await pdfDoc.getPage(pageNumber);
      const baseViewport = page.getViewport({ scale: 1 });
      const containerWidth = container.clientWidth;

      if (!containerWidth || !baseViewport.width) {
        if (!cancelled) setFitScaleReady(true);
        return;
      }

      const horizontalPadding = 48;
      const usableWidth = Math.max(containerWidth - horizontalPadding, 240);
      const nextScale = clamp(
        usableWidth / baseViewport.width,
        MIN_SCALE,
        MAX_SCALE,
      );

      if (cancelled) return;
      autoFitPendingRef.current = false;
      setScale((prev) =>
        Math.abs(prev - nextScale) < 0.01 ? prev : nextScale,
      );
      setFitScaleReady(true);
    }

    void prepareFitScale();
    return () => {
      cancelled = true;
    };
  }, [currentPage, numPages]);

  useEffect(() => {
    let cancelled = false;

    async function renderPage() {
      const pdfDoc = pdfDocRef.current;
      const canvas = canvasRef.current;
      if (!pdfDoc || !canvas || previewError) return;
      if (!fitScaleReady) return;
      if (currentPage < 1 || currentPage > pdfDoc.numPages) return;

      setPageRendering(true);
      setRenderedPageNumber((prev) => (prev === currentPage ? 0 : prev));

      try {
        renderTaskRef.current?.cancel?.();
        const page = await pdfDoc.getPage(currentPage);
        const viewport = page.getViewport({ scale });
        const context = canvas.getContext("2d");
        if (!context) {
          throw new Error("无法初始化 Canvas 上下文");
        }

        canvas.width = viewport.width;
        canvas.height = viewport.height;
        canvas.style.width = `${viewport.width}px`;
        canvas.style.height = `${viewport.height}px`;
        setPageSize({ width: viewport.width, height: viewport.height });

        const renderTask = page.render({
          canvasContext: context,
          viewport,
        });
        renderTaskRef.current = renderTask;
        await renderTask.promise;

        if (!cancelled) {
          if (latestRenderedPageRef.current !== currentPage) {
            latestRenderedPageRef.current = currentPage;
          }
          setRenderedPageNumber(currentPage);
          setPageInput(String(currentPage));
        }
      } catch (error) {
        if (!cancelled) {
          const message =
            error instanceof Error &&
            error.name === "RenderingCancelledException"
              ? null
              : error instanceof Error
                ? `页面渲染失败：${error.message}`
                : "页面渲染失败，请稍后重试。";
          if (message) setPreviewError(message);
        }
      } finally {
        if (!cancelled) {
          setPageRendering(false);
        }
      }
    }

    void renderPage();
    return () => {
      cancelled = true;
      renderTaskRef.current?.cancel?.();
    };
  }, [currentPage, fitScaleReady, previewError, scale]);

  useEffect(() => {
    return () => {
      pdfDocRef.current?.cleanup?.();
      void pdfDocRef.current?.destroy?.();
      pdfDocRef.current = null;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function resolveActiveTargetRect() {
      const pdfDoc = pdfDocRef.current;
      if (!pdfDoc || previewError) {
        setResolvedHighlightRect(null);
        return;
      }
      if (!followSectionTargetRef.current) {
        setResolvedHighlightRect(null);
        return;
      }
      if (!activeSectionLabel) {
        setResolvedHighlightRect(null);
        return;
      }

      const target = {
        number: activeSectionNumber,
        title: activeSectionTitle,
        label: activeSectionLabel,
      };

      const preferredPage =
        typeof anchorPage === "number" && !Number.isNaN(anchorPage)
          ? anchorPage + 1
          : currentPage;
      const pageOrder = [
        preferredPage,
        currentPage,
        ...Array.from({ length: pdfDoc.numPages }, (_, index) => index + 1),
      ].filter(
        (pageNumber, index, values) =>
          pageNumber >= 1 &&
          pageNumber <= pdfDoc.numPages &&
          values.indexOf(pageNumber) === index,
      );

      let bestMatch: {
        pageNumber: number;
        rect: HighlightRect;
        score: number;
      } | null = null;

      for (const pageNumber of pageOrder) {
        const page = await pdfDoc.getPage(pageNumber);
        const viewport = page.getViewport({ scale });
        const textMatch = await resolveRectFromPageTextOrAnnotations(
          page,
          viewport,
          target,
        );
        const bboxRect =
          typeof anchorPage === "number" && pageNumber === anchorPage + 1
            ? resolveRectFromBBox(
                anchorBBox,
                viewport.width,
                viewport.height,
                scale,
              )
            : null;
        const textScore =
          textMatch.rect === null
            ? Number.NEGATIVE_INFINITY
            : textMatch.score - (textMatch.isTocLikePage ? 300 : 0);
        const bboxScore =
          bboxRect === null
            ? Number.NEGATIVE_INFINITY
            : 220 + (pageNumber === preferredPage ? 60 : 0);

        const candidate =
          textScore >= bboxScore && textMatch.rect
            ? {
                pageNumber,
                rect: textMatch.rect,
                score: textScore,
              }
            : bboxRect
              ? {
                  pageNumber,
                  rect: bboxRect,
                  score: bboxScore,
                }
              : null;
        if (!candidate) continue;

        if (cancelled) return;
        if (!bestMatch || candidate.score > bestMatch.score) {
          bestMatch = candidate;
        }
      }

      if (bestMatch) {
        if (bestMatch.pageNumber !== currentPage) {
          setResolvedHighlightRect(null);
          setCurrentPage(bestMatch.pageNumber);
          setPageInput(String(bestMatch.pageNumber));
        } else {
          setResolvedHighlightRect(bestMatch.rect);
        }
        return;
      }

      if (cancelled) return;
      setResolvedHighlightRect(null);
      if (
        typeof anchorPage === "number" &&
        !Number.isNaN(anchorPage) &&
        currentPage !== anchorPage + 1
      ) {
        const fallbackPage = anchorPage + 1;
        setCurrentPage(fallbackPage);
        setPageInput(String(fallbackPage));
      }
    }

    void resolveActiveTargetRect();
    return () => {
      cancelled = true;
    };
  }, [
    activeSectionLabel,
    activeSectionNumber,
    activeSectionTitle,
    anchorBBox,
    anchorPage,
    currentPage,
    previewError,
    scale,
  ]);

  useEffect(() => {
    if (pageRendering || isChecking) return;
    if (!resolvedHighlightRect) {
      if (!scrollContainerRef.current) return;
      scrollContainerRef.current.scrollTo({
        top: 0,
        left: 0,
        behavior: "smooth",
      });
      return;
    }
    if (!highlightRef.current) return;

    const nextKey = [
      currentPage,
      activeSectionLabel ?? "",
      Math.round(resolvedHighlightRect.left),
      Math.round(resolvedHighlightRect.top),
      Math.round(resolvedHighlightRect.width),
      Math.round(resolvedHighlightRect.height),
    ].join(":");
    if (highlightScrollKeyRef.current === nextKey) return;
    highlightScrollKeyRef.current = nextKey;

    const frame = window.requestAnimationFrame(() => {
      highlightRef.current?.scrollIntoView({
        block: "center",
        inline: "center",
        behavior: "smooth",
      });
    });

    return () => window.cancelAnimationFrame(frame);
  }, [
    activeSectionLabel,
    currentPage,
    isChecking,
    pageRendering,
    resolvedHighlightRect,
  ]);

  const changePage = (nextPage: number) => {
    if (numPages <= 0) return;
    const clamped = Math.min(Math.max(nextPage, 1), numPages);
    if (clamped === currentPage) {
      setPageInput(String(clamped));
      return;
    }
    followSectionTargetRef.current = false;
    setResolvedHighlightRect(null);
    highlightScrollKeyRef.current = null;
    setCurrentPage(clamped);
    setPageInput(String(clamped));
    onManualPageChange?.(clamped - 1);
  };

  const submitPageInput = () => {
    const parsed = parseInt(pageInput, 10);
    if (Number.isNaN(parsed)) {
      setPageInput(String(currentPage));
      return;
    }
    changePage(parsed);
  };

  return (
    <div
      className="flex flex-col border-l border-gray-800 bg-gray-900"
      style={{ width: "58%" }}
    >
      <div className="shrink-0 flex items-center gap-3 px-4 py-2.5 border-b border-gray-800 bg-gray-950">
        <FileText size={14} className="text-gray-500 shrink-0" />
        <div className="min-w-0 flex-1">
          <div className="text-xs text-gray-400 truncate font-mono">
            {docId} — 原文预览
          </div>
          {activeSectionLabel && followSectionTargetRef.current && (
            <div className="text-[11px] text-indigo-300 truncate mt-0.5">
              当前章节：{activeSectionLabel}
            </div>
          )}
        </div>

        <div className="flex items-center gap-1.5 rounded-lg border border-gray-800 bg-gray-900 px-2 py-1">
          <button
            type="button"
            onClick={() => changePage(currentPage - 1)}
            disabled={currentPage <= 1}
            className="rounded p-1 text-gray-400 hover:bg-gray-800 hover:text-white disabled:opacity-40 disabled:hover:bg-transparent"
            title="上一页"
          >
            <ChevronLeft size={14} />
          </button>
          <input
            value={pageInput}
            onChange={(event) => setPageInput(event.target.value)}
            onBlur={submitPageInput}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                submitPageInput();
              }
            }}
            className="w-12 rounded bg-gray-950 px-1.5 py-0.5 text-center text-xs text-white outline-none"
          />
          <span className="text-xs text-gray-500">/ {numPages || "—"}</span>
          <button
            type="button"
            onClick={() => changePage(currentPage + 1)}
            disabled={numPages > 0 ? currentPage >= numPages : true}
            className="rounded p-1 text-gray-400 hover:bg-gray-800 hover:text-white disabled:opacity-40 disabled:hover:bg-transparent"
            title="下一页"
          >
            <ChevronRight size={14} />
          </button>
        </div>

        <div className="flex items-center gap-1.5 rounded-lg border border-gray-800 bg-gray-900 px-2 py-1">
          <button
            type="button"
            onClick={() => {
              autoFitPendingRef.current = false;
              setFitScaleReady(true);
              setScale((prev) => Math.max(MIN_SCALE, prev - 0.1));
            }}
            className="rounded px-2 py-0.5 text-sm text-gray-400 hover:bg-gray-800 hover:text-white"
            title="缩小"
          >
            -
          </button>
          <span className="w-14 text-center text-xs text-gray-300">
            {Math.round(scale * 100)}%
          </span>
          <button
            type="button"
            onClick={() => {
              autoFitPendingRef.current = false;
              setFitScaleReady(true);
              setScale((prev) => Math.min(MAX_SCALE, prev + 0.1));
            }}
            className="rounded px-2 py-0.5 text-sm text-gray-400 hover:bg-gray-800 hover:text-white"
            title="放大"
          >
            +
          </button>
        </div>

        {canDownload && (
          <button
            type="button"
            onClick={onDownload}
            className="p-1.5 rounded text-gray-500 hover:text-white hover:bg-gray-800 transition-colors"
            title="下载原文"
          >
            <Download size={13} />
          </button>
        )}
        <button
          type="button"
          onClick={onClose}
          className="p-1.5 rounded text-gray-500 hover:text-white hover:bg-gray-800 transition-colors"
          title="关闭预览"
        >
          <X size={14} />
        </button>
      </div>

      <div
        ref={scrollContainerRef}
        className="relative flex-1 overflow-auto bg-[#111827]"
      >
        {isChecking && !previewError && (
          <div className="absolute inset-0 flex items-center justify-center bg-gray-900/80 z-10">
            <Loader2 size={24} className="animate-spin text-gray-500" />
          </div>
        )}

        {previewError ? (
          <div className="flex flex-col items-center justify-center h-full gap-4 px-8 text-center">
            <AlertTriangle size={32} className="text-amber-500 shrink-0" />
            <div className="text-sm text-gray-300 leading-relaxed">
              {previewError}
            </div>
            {canDownload && (
              <button
                type="button"
                onClick={onDownload}
                className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg transition-colors"
              >
                <Download size={14} />
                下载原文
              </button>
            )}
          </div>
        ) : (
          <div className="min-h-full flex items-start justify-center p-6">
            <div
              className="relative shrink-0 rounded-sm shadow-2xl"
              style={{
                width: pageSize.width || undefined,
                height: pageSize.height || undefined,
              }}
            >
              <canvas ref={canvasRef} className="block bg-white" />
              {resolvedHighlightRect && (
                <div
                  ref={highlightRef}
                  className="absolute border-2 border-amber-400 bg-amber-300/20 shadow-[0_0_0_9999px_rgba(15,23,42,0.08)]"
                  style={resolvedHighlightRect}
                />
              )}
              {watermarkUrl && (
                <div
                  className="absolute inset-0 pointer-events-none"
                  style={{
                    backgroundImage: watermarkUrl,
                    backgroundRepeat: "repeat",
                    backgroundSize: "280px 140px",
                  }}
                />
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
