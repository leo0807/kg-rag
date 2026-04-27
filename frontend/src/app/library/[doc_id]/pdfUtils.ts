export type PdfDocumentProxy = {
  numPages: number;
  getPage: (pageNumber: number) => Promise<PdfPageProxy>;
  destroy?: () => Promise<void> | void;
  cleanup?: () => void;
};

export type PdfPageProxy = {
  getViewport: (args: { scale: number }) => {
    width: number;
    height: number;
    convertToViewportRectangle?: (rect: number[]) => number[];
  };
  getTextContent?: () => Promise<{
    items: Array<{ str?: string; width?: number; height?: number; transform?: number[] }>;
  }>;
  getAnnotations?: () => Promise<Array<{
    rect?: number[];
    contents?: string;
    title?: string;
    fieldValue?: string;
    alternativeText?: string;
  }>>;
  render: (args: { canvasContext: CanvasRenderingContext2D; viewport: { width: number; height: number } }) => { promise: Promise<void>; cancel?: () => void };
  cleanup?: () => void;
};

export type HighlightRect = { left: number; top: number; width: number; height: number };
export type ResolvedTargetMatch = { rect: HighlightRect | null; score: number; isTocLikePage: boolean };
export type SectionTarget = { number?: string; title?: string; label?: string };

export const MIN_SCALE = 0.6;
export const MAX_SCALE = 2.4;
export const DEFAULT_SCALE = 1.35;

export function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

export function normalizeHighlightRect(rect: HighlightRect, pageWidth: number, pageHeight: number): HighlightRect | null {
  if (pageWidth <= 0 || pageHeight <= 0) return null;
  if ([rect.left, rect.top, rect.width, rect.height].some(Number.isNaN)) return null;
  const left = clamp(rect.left, 0, pageWidth);
  const top = clamp(rect.top, 0, pageHeight);
  const right = clamp(rect.left + rect.width, 0, pageWidth);
  const bottom = clamp(rect.top + rect.height, 0, pageHeight);
  const width = right - left;
  const height = bottom - top;
  if (width <= 0 || height <= 0) return null;
  return { left, top, width: clamp(Math.max(12, width), 1, pageWidth - left), height: clamp(Math.max(10, height), 1, pageHeight - top) };
}

function scoreHighlightRect(rect: HighlightRect, pageWidth: number, pageHeight: number) {
  return Math.max(0, -rect.left) + Math.max(0, -rect.top) + Math.max(0, rect.left + rect.width - pageWidth) + Math.max(0, rect.top + rect.height - pageHeight);
}

export function normalizeMatchText(value: string | undefined | null) {
  return String(value ?? "").toLowerCase().replace(/[\s\u00a0.,;:!?'"()（）【】[\]{}<>《》、，。；：·•\-_/]+/g, "");
}

export function padHighlightRect(rect: HighlightRect, pageWidth: number, pageHeight: number, padding = 10): HighlightRect | null {
  return normalizeHighlightRect({ left: rect.left - padding, top: rect.top - padding, width: rect.width + padding * 2, height: rect.height + padding * 2 }, pageWidth, pageHeight);
}

export function unionHighlightRects(rects: HighlightRect[]): HighlightRect | null {
  if (rects.length === 0) return null;
  const left = Math.min(...rects.map((r) => r.left));
  const top = Math.min(...rects.map((r) => r.top));
  const right = Math.max(...rects.map((r) => r.left + r.width));
  const bottom = Math.max(...rects.map((r) => r.top + r.height));
  return { left, top, width: right - left, height: bottom - top };
}

export function resolveRectFromBBox(bbox: [number, number, number, number] | number[] | null | undefined, pageWidth: number, pageHeight: number, scale: number): HighlightRect | null {
  if (!Array.isArray(bbox) || bbox.length < 4 || pageWidth <= 0 || pageHeight <= 0) return null;
  const [x0, top, x1, bottom] = bbox.map((v) => (typeof v === "number" ? v : Number(v)));
  if ([x0, top, x1, bottom].some((v) => Number.isNaN(v))) return null;
  const unscaledPageHeight = pageHeight / scale;
  const rectWidth = Math.abs(x1 - x0) * scale;
  const rectHeight = Math.abs(bottom - top) * scale;
  const candidates: HighlightRect[] = [
    { left: Math.min(x0, x1) * scale, top: Math.min(top, bottom) * scale, width: rectWidth, height: rectHeight },
  ];
  if (unscaledPageHeight > 0) {
    candidates.push({ left: Math.min(x0, x1) * scale, top: (unscaledPageHeight - Math.max(top, bottom)) * scale, width: rectWidth, height: rectHeight });
  }
  const best = candidates
    .map((c) => ({ score: scoreHighlightRect(c, pageWidth, pageHeight), rect: normalizeHighlightRect(c, pageWidth, pageHeight) }))
    .filter((c): c is { score: number; rect: HighlightRect } => c.rect !== null)
    .sort((a, b) => a.score - b.score)[0];
  return best?.rect ?? null;
}

function isLikelyTocPage(rows: string[]) {
  if (rows.length === 0) return false;
  const norm = rows.map((r) => r.trim()).filter(Boolean);
  const fullText = norm.join("\n");
  if (/(^|\n)\s*(目录|目\s*录|contents?|table\s+of\s+contents)\s*($|\n)/i.test(fullText)) return true;
  const dottedRows = norm.filter((r) => /(\.{3,}|…{2,}|·{3,})/.test(r)).length;
  const indexRows = norm.filter((r) => /^\s*\d+(?:\.\d+)*\s+\S.+\d+\s*$/.test(r)).length;
  return dottedRows >= 3 || indexRows >= 5;
}

function toViewportRect(rect: number[], viewport: { width: number; height: number; convertToViewportRectangle?: (rect: number[]) => number[] }): HighlightRect | null {
  if (viewport.convertToViewportRectangle) {
    const [x0, y0, x1, y1] = viewport.convertToViewportRectangle(rect);
    return normalizeHighlightRect({ left: Math.min(x0, x1), top: Math.min(y0, y1), width: Math.abs(x1 - x0), height: Math.abs(y1 - y0) }, viewport.width, viewport.height);
  }
  return normalizeHighlightRect({ left: Math.min(rect[0], rect[2]), top: Math.min(rect[1], rect[3]), width: Math.abs(rect[2] - rect[0]), height: Math.abs(rect[3] - rect[1]) }, viewport.width, viewport.height);
}

export async function resolveRectFromPageTextOrAnnotations(page: PdfPageProxy, viewport: { width: number; height: number; convertToViewportRectangle?: (rect: number[]) => number[] }, target: SectionTarget): Promise<ResolvedTargetMatch> {
  const numberNorm = normalizeMatchText(target.number);
  const titleNorm = normalizeMatchText(target.title);
  const labelNorm = normalizeMatchText(target.label);
  const titlePrefix = titleNorm.slice(0, Math.min(titleNorm.length, 10));
  const needles = [labelNorm, `${numberNorm}${titleNorm}`, titleNorm, numberNorm].filter(Boolean);
  if (needles.length === 0) return { rect: null, score: Number.NEGATIVE_INFINITY, isTocLikePage: false };

  const candidates: Array<{ score: number; rect: HighlightRect }> = [];
  let isTocLikePage = false;

  if (page.getTextContent) {
    const textContent = await page.getTextContent();
    const groups = new Map<number, Array<{ str: string; x: number; rect: HighlightRect }>>();
    for (const item of textContent.items ?? []) {
      const str = String(item.str ?? "").trim();
      const transform = item.transform ?? [];
      if (!str || transform.length < 6) continue;
      const x = transform[4], y = transform[5];
      const width = Math.max(Number(item.width ?? 0), 2);
      const height = Math.max(Math.abs(Number(item.height ?? 0)), Math.abs(transform[3] ?? 0), 8);
      const rect = toViewportRect([x, y, x + width, y + height], viewport);
      if (!rect) continue;
      const key = Math.round(y / 2) * 2;
      const row = groups.get(key) ?? [];
      row.push({ str, x, rect });
      groups.set(key, row);
    }
    const orderedRows = [...groups.entries()].sort((a, b) => b[0] - a[0]).map(([, row]) => {
      const ordered = [...row].sort((a, b) => a.x - b.x);
      return { ordered, joined: ordered.map((item) => item.str).join(" ") };
    });
    isTocLikePage = isLikelyTocPage(orderedRows.map((row) => row.joined));
    for (const row of orderedRows) {
      const joinedNorm = normalizeMatchText(row.joined);
      let score = 0;
      if (labelNorm && joinedNorm.includes(labelNorm)) score += 140;
      if (titleNorm && joinedNorm.includes(titleNorm)) score += 120;
      if (numberNorm && joinedNorm.includes(numberNorm)) score += 40;
      if (numberNorm && titlePrefix && joinedNorm.includes(numberNorm) && joinedNorm.includes(titlePrefix)) score += 80;
      if (score <= 0) continue;
      const rect = unionHighlightRects(row.ordered.map((item) => item.rect));
      const padded = rect ? padHighlightRect(rect, viewport.width, viewport.height, 8) : null;
      if (padded) candidates.push({ score, rect: padded });
    }
  }

  if (page.getAnnotations) {
    const annotations = await page.getAnnotations();
    for (const ann of annotations ?? []) {
      const text = normalizeMatchText([ann.contents, ann.title, ann.fieldValue, ann.alternativeText].filter(Boolean).join(" "));
      if (!text || !ann.rect || ann.rect.length < 4) continue;
      let score = 0;
      if (labelNorm && text.includes(labelNorm)) score += 150;
      if (titleNorm && text.includes(titleNorm)) score += 130;
      if (numberNorm && text.includes(numberNorm)) score += 50;
      if (score <= 0) continue;
      const rect = toViewportRect(ann.rect, viewport);
      const padded = rect ? padHighlightRect(rect, viewport.width, viewport.height, 8) : null;
      if (padded) candidates.push({ score, rect: padded });
    }
  }

  candidates.sort((a, b) => b.score - a.score);
  return { rect: candidates[0]?.rect ?? null, score: candidates[0]?.score ?? Number.NEGATIVE_INFINITY, isTocLikePage };
}
