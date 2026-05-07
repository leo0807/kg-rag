"use client";

import { Check, PencilLine, X } from "lucide-react";
import Image from "next/image";
import { useEffect, useRef } from "react";

interface Props {
  content: string;
  images?: string[];
  onEditQuestion?: () => void;
  isEditing?: boolean;
  editValue?: string;
  onEditChange?: (v: string) => void;
  onEditSubmit?: () => void;
  onEditCancel?: () => void;
}

export function UserMessageBubble({
  content,
  images,
  onEditQuestion,
  isEditing,
  editValue,
  onEditChange,
  onEditSubmit,
  onEditCancel,
}: Props) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (isEditing) textareaRef.current?.focus();
  }, [isEditing]);

  if (isEditing) {
    return (
      <div className="mb-6 flex justify-end">
        <div className="relative group flex max-w-[75%] flex-col items-end gap-2">
          {images && images.length > 0 && (
            <div className="flex flex-wrap justify-end gap-2">
              {images.map((src, i) => (
                <Image
                  key={`${src.slice(0, 32)}_${i}`}
                  src={src}
                  alt=""
                  width={320}
                  height={256}
                  unoptimized
                  className="max-h-48 max-w-xs rounded-xl border border-indigo-500/30 bg-gray-900 object-contain"
                />
              ))}
            </div>
          )}
          <div className="w-full rounded-2xl rounded-tr-sm border border-indigo-500/30 bg-gray-950 px-4 py-3">
            <textarea
              ref={textareaRef}
              value={editValue ?? ""}
              onChange={(e) => onEditChange?.(e.target.value)}
              className="min-h-28 w-full resize-none bg-transparent text-sm leading-relaxed text-white outline-none placeholder-gray-500"
              placeholder="在这里修改问题"
              rows={4}
            />
            <div className="mt-3 flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={onEditCancel}
                className="inline-flex items-center gap-1 rounded-lg border border-gray-700 px-3 py-1.5 text-xs text-gray-400 transition-colors hover:border-gray-600 hover:text-gray-200"
              >
                <X size={12} />
                取消
              </button>
              <button
                type="button"
                onClick={onEditSubmit}
                className="inline-flex items-center gap-1 rounded-lg bg-[#1B6BB5] px-3 py-1.5 text-xs text-white transition-colors hover:bg-[#1558A0]"
              >
                <Check size={12} />
                保存
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="mb-6 flex justify-end">
      <div className="relative group flex max-w-[75%] flex-col items-end gap-2">
        {onEditQuestion && (
          <button
            type="button"
            onClick={onEditQuestion}
            className="absolute right-2 top-2 rounded-full border border-gray-800 bg-gray-950 p-1.5 text-gray-500 opacity-0 shadow-lg transition-all hover:border-indigo-500 hover:text-indigo-300 group-hover:opacity-100"
            title="编辑重答"
            aria-label="编辑重答"
          >
            <PencilLine size={12} />
          </button>
        )}
        {images && images.length > 0 && (
          <div className="flex flex-wrap justify-end gap-2">
            {images.map((src, i) => (
              <Image
                key={`${src.slice(0, 32)}_${i}`}
                src={src}
                alt=""
                width={320}
                height={256}
                unoptimized
                className="max-h-48 max-w-xs rounded-xl border border-indigo-500/30 bg-gray-900 object-contain"
              />
            ))}
          </div>
        )}
        {content && (
          <div className="rounded-2xl rounded-tr-sm bg-[#1B6BB5] px-4 py-3 pr-10">
            <p className="text-sm leading-relaxed text-white whitespace-pre-wrap">
              {content}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
