"use client";

import { Loader2, X } from "lucide-react";
import Image from "next/image";
import { useEffect, useMemo, useState } from "react";
import { fetchApi } from "@/lib/api";
import { imageFigureLabels } from "./imageRefs";
import type { AnswerImage } from "./types";

interface ImageDetail {
  image_id: string;
  doc_id: string | null;
  caption: string | null;
  description: string | null;
  drawing_summary: string | null;
  page: number | null;
  section_chunk_id: string | null;
  section_number: string | null;
  section_title: string | null;
  url: string | null;
  analyzed: boolean;
}

interface Props {
  image: AnswerImage;
  onClose: () => void;
  matchedFigureLabels?: string[];
}

function imageSrc(image: AnswerImage) {
  return image.url || `/api/images/${image.image_id}`;
}

export function AnswerImageLightbox({
  image,
  onClose,
  matchedFigureLabels = [],
}: Props) {
  const [detail, setDetail] = useState<ImageDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const src = useMemo(() => imageSrc(image), [image]);
  const labels = useMemo(() => imageFigureLabels(image), [image]);
  const matched = matchedFigureLabels.filter((label) => labels.includes(label));

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchApi<ImageDetail>(
      `/api/images/${encodeURIComponent(image.image_id)}/detail`,
    )
      .then((data) => {
        if (!cancelled) setDetail(data);
      })
      .catch(() => {
        if (!cancelled) setDetail(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [image.image_id]);

  return (
    <div className="fixed inset-0 z-[220] flex items-center justify-center px-4 py-6 backdrop-blur-sm">
      <button
        type="button"
        aria-label="关闭图片预览"
        className="absolute inset-0 z-0 cursor-zoom-out bg-black/80"
        onClick={onClose}
      />
      <div className="relative z-10 flex max-h-[92vh] w-full max-w-5xl overflow-hidden rounded-2xl border border-gray-800 bg-gray-950 shadow-2xl">
        <div className="flex min-h-0 flex-[1.3] items-center justify-center bg-black/70 p-4">
          <div className="relative h-full min-h-[40vh] w-full">
            {loading ? (
              <div className="flex h-full items-center justify-center text-gray-500">
                <Loader2 size={24} className="animate-spin" />
              </div>
            ) : (
              <Image
                src={src}
                alt={detail?.caption || image.caption || image.image_id}
                fill
                unoptimized
                className="object-contain"
                sizes="(max-width: 768px) 100vw, 70vw"
              />
            )}
          </div>
        </div>

        <div className="flex max-h-[92vh] w-[360px] shrink-0 flex-col border-l border-gray-800 bg-gray-900">
          <div className="flex items-center justify-between border-b border-gray-800 px-4 py-3">
            <div className="min-w-0">
              <div className="truncate text-sm font-semibold text-gray-100">
                {detail?.caption || image.caption || image.image_id}
              </div>
              <div className="mt-0.5 text-[10px] text-gray-500">
                {image.doc_id}
                {detail?.page || image.page_num
                  ? ` · 第${detail?.page ?? image.page_num}页`
                  : ""}
              </div>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-gray-700 p-1.5 text-gray-300 transition-colors hover:bg-gray-800 hover:text-gray-100"
              title="关闭"
            >
              <X size={16} />
            </button>
          </div>

          <div className="flex-1 space-y-3 overflow-y-auto px-4 py-3 text-sm">
            {matched.length > 0 && (
              <div className="rounded-lg border border-amber-700/40 bg-amber-950/30 px-3 py-2 text-xs text-amber-200">
                匹配到答案中的图号：{matched.join("、")}
              </div>
            )}

            {labels.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {labels.map((label) => (
                  <span
                    key={label}
                    className={`rounded-full border px-2 py-0.5 text-[10px] ${
                      matched.includes(label)
                        ? "border-amber-500/60 bg-amber-900/40 text-amber-200"
                        : "border-gray-700 bg-gray-800/60 text-gray-300"
                    }`}
                  >
                    {label}
                  </span>
                ))}
              </div>
            )}

            <div>
              <div className="mb-1 text-[10px] uppercase tracking-wide text-gray-500">
                对应文字
              </div>
              <div className="rounded-lg border border-gray-800 bg-gray-950/80 p-3 text-xs leading-relaxed text-gray-300">
                {detail?.description ||
                  image.description ||
                  detail?.drawing_summary ||
                  "暂无文字说明"}
              </div>
            </div>

            <div className="space-y-2 rounded-lg border border-gray-800 bg-gray-950/60 p-3 text-xs text-gray-300">
              <div className="flex items-center justify-between gap-2">
                <span className="text-gray-500">所属章节</span>
                <span className="truncate text-right font-mono text-gray-400">
                  {detail?.section_number || image.figure_label || "—"}
                </span>
              </div>
              <div className="text-gray-400">
                {detail?.section_title || "未获取到章节标题"}
              </div>
              <div className="flex items-center justify-between gap-2">
                <span className="text-gray-500">页码</span>
                <span className="font-mono text-gray-400">
                  {detail?.page || image.page_num || "—"}
                </span>
              </div>
            </div>

            <div className="rounded-lg border border-gray-800 bg-gray-950/60 p-3 text-xs leading-relaxed text-gray-400">
              {detail?.drawing_summary || "暂无图纸摘要"}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
