"use client";
import { useState, useEffect, useCallback } from "react";
import { fetchApi } from "@/lib/api";
import type { Conversation, Message, Strategy } from "./types";

export function useConversations() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [loadingConvs, setLoadingConvs] = useState(true);

  // 从后端加载会话列表（同时清理空会话）
  const fetchConversations = useCallback(async () => {
    try {
      const data = await fetchApi<Conversation[]>("/api/conversations");
      const list = Array.isArray(data) ? data : [];

      // 删除后端残留的空会话（无消息）
      const emptyIds = list
        .filter(
          (c: { messages: unknown[] }) =>
            !c.messages || c.messages.length === 0,
        )
        .map((c: { id: string }) => c.id);
      if (emptyIds.length > 0) {
        await Promise.all(
          emptyIds.map((id: string) =>
            fetchApi(`/api/conversations/${id}`, {
              method: "DELETE",
            }).catch(() => {}),
          ),
        );
        setActiveId((prev) => (emptyIds.includes(prev ?? "") ? null : prev));
      }

      setConversations(
        list.filter(
          (c: { messages: unknown[] }) => c.messages && c.messages.length > 0,
        ),
      );
      // 不自动选中历史会话，保持 null → 进入新建对话模式
    } catch (e) {
      console.error("加载会话失败", e);
      setConversations([]);
    } finally {
      setLoadingConvs(false);
    }
  }, []);

  useEffect(() => {
    fetchConversations();
  }, [fetchConversations]);

  const activeConv = conversations.find((c) => c.id === activeId) ?? null;

  // 创建新会话
  async function createConversation(
    title: string = "新对话",
    strategy: Strategy = "parallel",
  ): Promise<string> {
    const conv = await fetchApi<Conversation>("/api/conversations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title, strategy }),
    });
    setConversations((prev) => [conv, ...prev]);
    setActiveId(conv.id);
    return conv.id;
  }

  // 更新会话消息
  async function updateConversation(
    convId: string,
    messages: Message[],
    title?: string,
  ) {
    // 先更新本地
    setConversations((prev) =>
      prev.map((c) =>
        c.id === convId
          ? {
              ...c,
              messages,
              title: title ?? c.title,
              updated_at: new Date().toISOString(),
            }
          : c,
      ),
    );
    // 再持久化
    try {
      await fetchApi(`/api/conversations/${convId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages, title: title ?? "" }),
      });
    } catch (e) {
      console.error("保存会话失败", e);
    }
  }

  // 删除会话
  async function deleteConversation(convId: string) {
    await fetchApi(`/api/conversations/${convId}`, {
      method: "DELETE",
    });
    const updated = conversations.filter((c) => c.id !== convId);
    setConversations(updated);
    if (activeId === convId) {
      setActiveId(updated[0]?.id ?? null);
    }
  }

  // 清空当前会话消息
  async function clearConversation() {
    if (!activeId) return;
    await updateConversation(activeId, [], "新对话");
  }

  return {
    conversations,
    activeId,
    activeConv,
    loadingConvs,
    setActiveId,
    createConversation,
    updateConversation,
    deleteConversation,
    clearConversation,
    refetch: fetchConversations,
  };
}
