"use client";

import { ThumbsUp, ThumbsDown, ClipboardList } from "lucide-react";

interface Props {
  onThumbsUp: () => void;
  onThumbsDown: () => void;
  onAnnotate: () => void;
  disabled?: boolean;
}

export function FeedbackButtons({ onThumbsUp, onThumbsDown, onAnnotate, disabled }: Props) {
  return (
    <div className="flex items-center gap-1">
      <button
        type="button"
        onClick={onThumbsUp}
        disabled={disabled}
        title="有帮助"
        className="flex items-center gap-1 px-2 py-1 text-xs text-gray-500 hover:text-emerald-400 hover:bg-emerald-400/10 rounded-md transition-colors disabled:opacity-40"
      >
        <ThumbsUp size={13} />
        <span>有帮助</span>
      </button>
      <button
        type="button"
        onClick={onThumbsDown}
        disabled={disabled}
        title="有问题"
        className="flex items-center gap-1 px-2 py-1 text-xs text-gray-500 hover:text-red-400 hover:bg-red-400/10 rounded-md transition-colors disabled:opacity-40"
      >
        <ThumbsDown size={13} />
        <span>有问题</span>
      </button>
      <button
        type="button"
        onClick={onAnnotate}
        disabled={disabled}
        title="详细标注"
        className="flex items-center gap-1 px-2 py-1 text-xs text-gray-500 hover:text-blue-400 hover:bg-blue-400/10 rounded-md transition-colors disabled:opacity-40"
      >
        <ClipboardList size={13} />
        <span>标注</span>
      </button>
    </div>
  );
}
