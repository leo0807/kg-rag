"use client";

import Image from "next/image";
import { useMemo, useState } from "react";
import { AnswerImageLightbox } from "./AnswerImageLightbox";
import {
  extractFigureLabels,
  imageFigureLabels,
  imageMatchesFigureLabels,
} from "./imageRefs";
import type { AnswerImage } from "./types";

interface Props {
  images: AnswerImage[];
  title?: string;
  limit?: number;
  contextText?: string;
}

function imageSrc(image: AnswerImage) {
  return image.url || `/api/images/${image.image_id}`;
}

export function AnswerImageGallery({
  images,
  title = "相关图示",
  limit = 6,
  contextText,
}: Props) {
  const [selectedImage, setSelectedImage] = useState<AnswerImage | null>(null);
  const contextLabels = useMemo(
    () => extractFigureLabels(contextText),
    [contextText],
  );
  if (!images.length) return null;
  return (
    <>
      <div className="mt-3 border-t border-gray-800 pt-3">
        <div className="mb-2 text-xs text-gray-500">{title}</div>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          {images.slice(0, limit).map((img) => {
            const src = imageSrc(img);
            const caption = img.caption || img.description || img.image_id;
            const matched = imageMatchesFigureLabels(img, contextLabels);
            const figureLabel =
              imageFigureLabels(img)[0] || img.figure_label || "";
            return (
              <button
                key={img.image_id}
                type="button"
                onClick={() => setSelectedImage(img)}
                className={`group w-full overflow-hidden rounded-lg border bg-gray-950/60 text-left transition-colors hover:border-indigo-500/60 ${
                  matched
                    ? "border-amber-500/70 ring-1 ring-amber-500/30"
                    : "border-gray-800"
                }`}
                title={`${img.doc_id}${img.page_num ? ` 第${img.page_num}页` : ""}`}
              >
                <div className="relative h-24 w-full overflow-hidden">
                  <Image
                    src={src}
                    alt={caption}
                    fill
                    unoptimized
                    className="object-cover transition-transform group-hover:scale-[1.02]"
                  />
                  {figureLabel && (
                    <div
                      className={`absolute left-1 top-1 rounded-full px-1.5 py-0.5 text-[9px] font-semibold ${
                        matched
                          ? "bg-amber-500/90 text-black"
                          : "bg-black/70 text-gray-100 ring-1 ring-gray-600/60"
                      }`}
                    >
                      {figureLabel}
                    </div>
                  )}
                </div>
                <div className="px-2 py-1 text-[10px] text-gray-500 line-clamp-2">
                  {caption}
                </div>
              </button>
            );
          })}
        </div>
      </div>
      {selectedImage && (
        <AnswerImageLightbox
          image={selectedImage}
          onClose={() => setSelectedImage(null)}
          matchedFigureLabels={contextLabels}
        />
      )}
    </>
  );
}
