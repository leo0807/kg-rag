"use client";

import { Reply, X } from "lucide-react";
import Image from "next/image";
import type { SourceSection } from "./types";

interface Props {
  quoteSource?: SourceSection | null;
  pendingImages: string[];
  onClearQuote?: () => void;
  onRemoveImage: (idx: number) => void;
}

export function ConversationInputStatusBars({
  quoteSource,
  pendingImages,
  onClearQuote,
  onRemoveImage,
}: Props) {
  return (
    <>
      {quoteSource && (
        <div className="mb-2 flex items-start gap-2.5 rounded-xl border border-indigo-700/50 bg-indigo-950/60 px-3 py-2">
          <Reply size={13} className="shrink-0 text-indigo-400 mt-0.5" />
          <div className="min-w-0 flex-1">
            <div className="text-xs font-medium leading-snug text-indigo-300">
              追问引用 ·{" "}
              <span className="font-mono">
                {quoteSource.doc_id} §{quoteSource.number}
              </span>
            </div>
            <div className="mt-0.5 truncate text-xs text-indigo-400/70">
              {quoteSource.title}
            </div>
          </div>
          <button
            type="button"
            onClick={onClearQuote}
            className="shrink-0 text-indigo-600 transition-colors hover:text-indigo-300 mt-0.5"
            title="取消引用"
          >
            <X size={12} />
          </button>
        </div>
      )}

      {pendingImages.length > 0 && (
        <div className="mb-2 flex flex-wrap gap-2 px-1">
          {pendingImages.map((src, idx) => (
            <div key={src} className="group relative">
              <Image
                src={src}
                alt=""
                width={64}
                height={64}
                unoptimized
                className="h-16 w-16 rounded-lg border border-gray-700 object-cover"
              />
              <button
                type="button"
                onClick={() => onRemoveImage(idx)}
                className="absolute -right-1.5 -top-1.5 flex h-4 w-4 items-center justify-center rounded-full border border-gray-600 bg-gray-800 opacity-0 transition-opacity hover:bg-red-900 group-hover:opacity-100"
              >
                <X size={9} className="text-gray-300" />
              </button>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
