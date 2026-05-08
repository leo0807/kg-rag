"use client";

import { useState } from "react";

export function useInlineQuestionEdit() {
  const [editingMessageIndex, setEditingMessageIndex] = useState<number | null>(
    null,
  );
  const [editingMessageDraft, setEditingMessageDraft] = useState("");

  function startEdit(messageIndex: number, content: string) {
    setEditingMessageIndex(messageIndex);
    setEditingMessageDraft(content);
  }

  function cancelEdit() {
    setEditingMessageIndex(null);
    setEditingMessageDraft("");
  }

  return {
    editingMessageIndex,
    editingMessageDraft,
    setEditingMessageDraft,
    startEdit,
    cancelEdit,
  };
}
