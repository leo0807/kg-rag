"use client";

import { Loader2, Pencil, Ruler } from "lucide-react";

interface Annotation { type: string; raw: string; parameter: string; value: string; value_max: string; value_min: string; unit: string }

export interface DrawingImage {
  image_id: string; caption: string; path: string; minio_path: string | null;
  url: string | null; description: string; is_drawing: boolean;
  part_numbers: string[]; annotations: Annotation[]; assembly_relations: string[];
  drawing_summary: string; annotations_count: number;
  section_chunk_id: string | null; section_number: string | null; section_title: string | null;
}

interface Props {
  img:         DrawingImage;
  reanalyzing: boolean;
  onSelect:    (img: DrawingImage) => void;
}

export function DrawingCard({ img, reanalyzing, onSelect }: Props) {
  const src = img.url ?? null;
  return (
    <button
      id={`image-${img.image_id}`}
      type="button"
      onClick={() => onSelect(img)}
      className="group relative bg-gray-900 border border-gray-800 rounded-xl overflow-hidden hover:border-indigo-500 transition-colors text-left"
    >
      <div className="aspect-[4/3] overflow-hidden bg-gray-800 flex items-center justify-center">
        {src ? (
          <img
            src={src}
            alt={img.caption || "图片"}
            loading="lazy"
            decoding="async"
            className="w-full h-full object-contain group-hover:scale-105 transition-transform duration-200"
            onError={(e) => {
              (e.currentTarget as HTMLImageElement).style.display = "none";
              (e.currentTarget.nextSibling as HTMLElement | null)?.removeAttribute("hidden");
            }}
          />
        ) : null}
        <span hidden={!!src} className="text-xs text-gray-600 px-3 text-center">图片暂不可用</span>
      </div>
      <div className="px-3 py-2">
        <div className="flex items-center gap-1.5 mb-0.5">
          {img.is_drawing && <Ruler size={10} className="text-indigo-400 shrink-0" />}
          <span className="text-xs text-gray-300 truncate">
            {img.caption || img.drawing_summary || "图片"}
          </span>
        </div>
        <div className="flex items-center justify-between gap-2">
          <span className="text-xs text-gray-600 font-mono truncate">
            {img.section_number ? `§${img.section_number}` : "未归属章节"}
          </span>
          <div className="flex items-center gap-1.5 shrink-0">
            {img.annotations_count > 0 && (
              <span className="text-xs text-indigo-400">{img.annotations_count} 条标注</span>
            )}
            {reanalyzing && <Loader2 size={10} className="animate-spin text-amber-400" />}
          </div>
        </div>
      </div>
      {!img.annotations_count && (
        <div className="absolute top-2 right-2 p-1 bg-gray-900/80 rounded" title="未提取到尺寸标注">
          <Pencil size={10} className="text-gray-500" />
        </div>
      )}
    </button>
  );
}

