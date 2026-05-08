"use client";
import { useCallback, useEffect, useRef } from "react";
import { useFavorites } from "@/app/favorites/useFavorites";
import { ConversationInputComposer } from "./ConversationInputComposer";
import { ConversationInputStatusBars } from "./ConversationInputStatusBars";
import { StrategySelector } from "./StrategySelector";
import type { SourceSection, Strategy } from "./types";

interface Props {
  value: string;
  loading: boolean;
  streaming: boolean;
  onStop?: () => void;
  pendingImages: string[];
  quoteSource?: SourceSection | null;
  onChange: (v: string) => void;
  onSubmit: () => void;
  onClear: () => void;
  onAddImages: (imgs: string[]) => void;
  onRemoveImage: (idx: number) => void;
  onClearQuote?: () => void;
  strategy: Strategy;
  onStrategy: (s: Strategy) => void;
  useHyde: boolean;
  onHydeToggle: (v: boolean) => void;
  historyLen: number;
}

export default function ConversationInput({
  value,
  loading,
  streaming,
  onStop,
  pendingImages,
  quoteSource,
  onChange,
  onSubmit,
  onAddImages,
  onRemoveImage,
  onClearQuote,
  onClear,
  strategy,
  onStrategy,
  useHyde,
  onHydeToggle,
  historyLen,
}: Props) {
  const { getFavoriteId, addFavorite, removeFavorite } = useFavorites();
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    textareaRef.current?.focus();
  }, []);
  useEffect(() => {
    if (quoteSource) textareaRef.current?.focus();
  }, [quoteSource]);

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey && !loading && !streaming) {
      e.preventDefault();
      onSubmit();
    }
  }

  const readFilesAsBase64 = useCallback(
    (files: File[]) => {
      const imageFiles = files.filter((f) => f.type.startsWith("image/"));
      if (!imageFiles.length) return;
      Promise.all(
        imageFiles.map(
          (f) =>
            new Promise<string>((resolve, reject) => {
              const reader = new FileReader();
              reader.onload = () => resolve(reader.result as string);
              reader.onerror = reject;
              reader.readAsDataURL(f);
            }),
        ),
      )
        .then(onAddImages)
        .catch(() => {});
    },
    [onAddImages],
  );

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    if (e.target.files) readFilesAsBase64(Array.from(e.target.files));
    e.target.value = "";
  }

  function handlePaste(e: React.ClipboardEvent) {
    const files = Array.from(e.clipboardData.items)
      .filter((item) => item.kind === "file" && item.type.startsWith("image/"))
      .map((item) => item.getAsFile())
      .filter(Boolean) as File[];
    if (files.length) readFilesAsBase64(files);
  }

  const canSend =
    Boolean(value.trim() || pendingImages.length > 0) && !loading && !streaming;

  return (
    <div className="border-t border-gray-800 bg-gray-950 px-4 py-4 relative">
      <ConversationInputStatusBars
        quoteSource={quoteSource}
        pendingImages={pendingImages}
        onClearQuote={onClearQuote}
        onRemoveImage={onRemoveImage}
      />
      <div className="mb-3">
        <StrategySelector
          strategy={strategy}
          useHyde={useHyde}
          historyLen={historyLen}
          onStrategy={onStrategy}
          onHydeToggle={onHydeToggle}
          onClear={onClear}
        />
      </div>
      <ConversationInputComposer
        value={value}
        loading={loading}
        streaming={streaming}
        onStop={onStop}
        canSend={canSend}
        onSubmit={onSubmit}
        onFileClick={() => fileInputRef.current?.click()}
        onFileChange={handleFileChange}
        onPaste={handlePaste}
        onKeyDown={handleKeyDown}
        onInput={(e) => {
          const el = e.currentTarget;
          el.style.height = "auto";
          el.style.height = `${Math.min(el.scrollHeight, 128)}px`;
        }}
        onChange={onChange}
        fileInputRef={fileInputRef}
        textareaRef={textareaRef}
        isFavorited={Boolean(
          getFavoriteId({ type: "query", query_text: value.trim() }),
        )}
        onToggleFavorite={async () => {
          const trimmed = value.trim();
          const favId = getFavoriteId({
            type: "query",
            query_text: trimmed,
          });
          if (favId) await removeFavorite(favId);
          else
            await addFavorite({
              type: "query",
              query_text: trimmed,
              title: trimmed.slice(0, 80),
            });
        }}
      />
      <div className="text-xs text-gray-700 text-center mt-2">
        CPS 知识库可能存在错误，请以原始规范为准
      </div>
    </div>
  );
}
