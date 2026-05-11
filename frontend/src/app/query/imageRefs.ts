"use client";

import type { AnswerImage } from "./types";

const FIGURE_RE = /(?:图|Figure|Fig\.?)\s*([0-9]+(?:[-.][0-9]+)+|[0-9]+-\d+)/gi;

function normalizeFigureLabel(raw: string) {
  const value = raw.trim().replace(/\./g, "-");
  return value ? `图${value}` : "";
}

export function extractFigureLabels(text?: string | null): string[] {
  if (!text) return [];
  const labels = new Set<string>();
  for (const match of text.matchAll(FIGURE_RE)) {
    const label = normalizeFigureLabel(match[1] ?? "");
    if (label) labels.add(label);
  }
  return [...labels];
}

export function imageFigureLabels(image: AnswerImage): string[] {
  const labels = new Set<string>();
  for (const label of image.figure_labels ?? []) {
    const normalized = normalizeFigureLabel(label.replace(/^图/, ""));
    if (normalized) labels.add(normalized);
  }
  for (const label of extractFigureLabels(
    [image.figure_label, image.caption, image.description]
      .filter(Boolean)
      .join(" "),
  )) {
    labels.add(label);
  }
  return [...labels];
}

export function imageMatchesFigureLabels(image: AnswerImage, labels: string[]) {
  if (!labels.length) return false;
  const imageLabels = imageFigureLabels(image);
  return imageLabels.some((label) => labels.includes(label));
}
