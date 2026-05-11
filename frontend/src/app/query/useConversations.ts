"use client";
import { useCallback, useEffect, useState } from "react";
import { fetchApi } from "@/lib/api";
import type { Conversation, Message, Strategy } from "./types";

const ACTIVE_CONVERSATION_KEY = "query:active_conversation_id";
const CONVERSATION_SNAPSHOT_PREFIX = "query:conversation_snapshot:";

function getConversationSnapshot(convId: string): Conversation | null {
  if (typeof window === "undefined" || !convId) return null;
  try {
    const raw = localStorage.getItem(`${CONVERSATION_SNAPSHOT_PREFIX}${convId}`);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Conversation;
    return parsed?.id === convId ? parsed : null;
  } catch {
    return null;
  }
}

function setConversationSnapshot(conv: Conversation) {
  if (typeof window === "undefined" || !conv?.id) return;
  try {
    localStorage.setItem(
      `${CONVERSATION_SNAPSHOT_PREFIX}${conv.id}`,
      JSON.stringify(conv),
    );
  } catch {
    void 0;
  }
}

function removeConversationSnapshot(convId: string) {
  if (typeof window === "undefined" || !convId) return;
  try {
    localStorage.removeItem(`${CONVERSATION_SNAPSHOT_PREFIX}${convId}`);
  } catch {
    void 0;
  }
}

export function useConversations() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveIdState] = useState<string | null>(() => {
    if (typeof window === "undefined") return null;
    return localStorage.getItem(ACTIVE_CONVERSATION_KEY) || null;
  });
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
        list
          .filter(
            (c: { messages: unknown[] }) => c.messages && c.messages.length > 0,
          )
          .map((conv) => {
            const snapshot = getConversationSnapshot(conv.id);
            if (
              snapshot &&
              (snapshot.messages?.length ?? 0) > (conv.messages?.length ?? 0)
            ) {
              return snapshot;
            }
            return conv;
          }),
      );
      if (typeof window !== "undefined") {
        const storedActiveId = localStorage.getItem(ACTIVE_CONVERSATION_KEY);
        const candidate =
          storedActiveId &&
          list.some((c: { id: string }) => c.id === storedActiveId)
            ? storedActiveId
            : null;
        setActiveIdState(candidate);
      }
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

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (activeId) localStorage.setItem(ACTIVE_CONVERSATION_KEY, activeId);
    else localStorage.removeItem(ACTIVE_CONVERSATION_KEY);
  }, [activeId]);

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
    setActiveIdState(conv.id);
    return conv.id;
  }

  // 更新会话消息
  async function updateConversation(
    convId: string,
    messages: Message[],
    title?: string,
  ) {
    const prevConv = conversations.find((c) => c.id === convId);
    const nextConv = {
      id: convId,
      title: title ?? prevConv?.title ?? "新对话",
      messages,
      strategy: prevConv?.strategy ?? "parallel",
      created_at: prevConv?.created_at ?? new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
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
    setConversationSnapshot(nextConv as Conversation);
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
    const shouldCreateEmpty = activeId === convId;
    await fetchApi(`/api/conversations/${convId}`, {
      method: "DELETE",
    });
    removeConversationSnapshot(convId);
    const updated = conversations.filter((c) => c.id !== convId);
    setConversations(updated);
    if (shouldCreateEmpty) {
      await createConversation("新对话");
      return;
    }
    if (activeId === convId) setActiveIdState(updated[0]?.id ?? null);
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
    setActiveId: setActiveIdState,
    createConversation,
    updateConversation,
    deleteConversation,
    clearConversation,
    refetch: fetchConversations,
  };
}
