"use client";

import { useEffect } from "react";

interface Options {
  onNewConversation: () => void;
  onFocusInput: () => void;
  onStop?: () => void;
  streaming: boolean;
}

/**
 * 查询页全局键盘快捷键：
 *   ⌘/Ctrl+N  — 新建对话
 *   ⌘/Ctrl+K  — 聚焦输入框
 *   Esc        — 停止流式输出（streaming 时）
 */
export function useKeyboardShortcuts({ onNewConversation, onFocusInput, onStop, streaming }: Options) {
  useEffect(() => {
    function handler(e: KeyboardEvent) {
      const meta = e.metaKey || e.ctrlKey;

      if (meta && e.key === "n" && !e.shiftKey) {
        const active = document.activeElement as HTMLElement | null;
        const inInput = active?.tagName === "TEXTAREA" || active?.tagName === "INPUT";
        if (!inInput) {
          e.preventDefault();
          onNewConversation();
        }
        return;
      }

      if (meta && e.key === "k") {
        e.preventDefault();
        onFocusInput();
        return;
      }

      if (e.key === "Escape" && streaming && onStop) {
        onStop();
        return;
      }
    }

    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onNewConversation, onFocusInput, onStop, streaming]);
}
