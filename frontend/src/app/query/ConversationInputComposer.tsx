"use client";

import { Paperclip, Send, Square, Star } from "lucide-react";
import type {
  ChangeEvent,
  ClipboardEvent,
  FormEvent,
  KeyboardEvent,
  MutableRefObject,
} from "react";

interface Props {
  value: string;
  loading: boolean;
  streaming: boolean;
  onStop?: () => void;
  canSend: boolean;
  onSubmit: () => void;
  onFileClick: () => void;
  onFileChange: (e: ChangeEvent<HTMLInputElement>) => void;
  onPaste: (e: ClipboardEvent) => void;
  onKeyDown: (e: KeyboardEvent) => void;
  onInput: (e: FormEvent<HTMLTextAreaElement>) => void;
  onChange: (v: string) => void;
  fileInputRef: MutableRefObject<HTMLInputElement | null>;
  textareaRef: MutableRefObject<HTMLTextAreaElement | null>;
  isFavorited: boolean;
  onToggleFavorite: () => void;
}

export function ConversationInputComposer({
  value,
  loading,
  streaming,
  onStop,
  canSend,
  onSubmit,
  onFileClick,
  onFileChange,
  onPaste,
  onKeyDown,
  onInput,
  onChange,
  fileInputRef,
  textareaRef,
  isFavorited,
  onToggleFavorite,
}: Props) {
  return (
    <div className="flex items-end gap-2 rounded-2xl border border-gray-700 bg-gray-900 px-3 py-3 transition-colors focus-within:border-[#1B6BB5] sm:px-3.5 sm:py-3.5">
      <button
        type="button"
        onClick={onFileClick}
        disabled={loading || streaming}
        className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-gray-500 transition-colors hover:bg-gray-800 hover:text-gray-300 disabled:opacity-30"
        title="上传图片"
      >
        <Paperclip size={15} />
      </button>
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        multiple
        className="hidden"
        onChange={onFileChange}
      />
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={onKeyDown}
        onPaste={onPaste}
        placeholder="发送消息或粘贴图片... （Enter 发送，Shift+Enter 换行）"
        rows={1}
        className="max-h-32 flex-1 resize-none bg-transparent text-sm leading-relaxed text-gray-200 outline-none placeholder-gray-600"
        style={{ height: "auto" }}
        onInput={onInput}
      />
      {value.trim() && !streaming && (
        <button
          type="button"
          onClick={onToggleFavorite}
          title={isFavorited ? "取消收藏此问题" : "收藏此问题"}
          className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg transition-colors hover:bg-gray-800"
        >
          <Star
            size={13}
            className={
              isFavorited
                ? "text-amber-400 fill-amber-400"
                : "text-gray-600 hover:text-amber-400"
            }
          />
        </button>
      )}
      {streaming && onStop ? (
        <button
          type="button"
          onClick={onStop}
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-red-600/80 transition-colors hover:bg-red-600"
          title="停止生成"
        >
          <Square size={12} className="fill-white text-white" />
        </button>
      ) : (
        <button
          type="button"
          onClick={onSubmit}
          disabled={!canSend}
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-[#1B6BB5] transition-colors hover:bg-[#1558A0] disabled:cursor-not-allowed disabled:opacity-40"
        >
          <Send size={14} className="text-white" />
        </button>
      )}
    </div>
  );
}
