"use client";

import { ChevronLeft, ChevronRight, Folder, Plus, Search, X } from "lucide-react";
import { useEffect, useState } from "react";
import { ConversationCard } from "./ConversationCard";
import type { Conversation, ConversationCategory } from "./types";
import { fetchApi } from "@/lib/api";

interface Props {
  conversations: Conversation[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  onNew: () => void;
  onRefresh?: () => void;
  disableNew?: boolean;
  mobile?: boolean;
  onClose?: () => void;
}

const STORAGE_KEY = "conv_sidebar_collapsed";

export default function ConversationSidebar({
  conversations, activeId, onSelect, onDelete, onNew, onRefresh,
  disableNew = false, mobile = false, onClose,
}: Props) {
  const [collapsed, setCollapsed] = useState(false);
  const [query, setQuery] = useState("");
  const [activeCat, setActiveCat] = useState<string | null>(null);
  const [categories, setCategories] = useState<ConversationCategory[]>([]);
  const effectiveCollapsed = mobile ? false : collapsed;

  useEffect(() => {
    if (localStorage.getItem(STORAGE_KEY) === "1") setCollapsed(true);
  }, []);

  useEffect(() => {
    fetchApi<ConversationCategory[]>("/api/conversations/categories")
      .then(setCategories)
      .catch(() => {});
  }, []);

  function toggle() {
    setCollapsed((v) => {
      const next = !v;
      localStorage.setItem(STORAGE_KEY, next ? "1" : "0");
      return next;
    });
  }

  async function handlePin(id: string) {
    await fetchApi(`/api/conversations/${id}/pin`, { method: "PUT" });
    onRefresh?.();
  }

  async function handleArchive(id: string) {
    await fetchApi(`/api/conversations/${id}/archive`, { method: "PUT" });
    onRefresh?.();
  }

  const filtered = conversations
    .filter((c) => c.id && !c.is_archived)
    .filter((c) => !activeCat || c.category_id === activeCat)
    .filter((c) => !query || c.title.toLowerCase().includes(query.toLowerCase()))
    .sort((a, b) => (b.is_pinned ? 1 : 0) - (a.is_pinned ? 1 : 0));

  return (
    <aside
      className={`shrink-0 border-r border-gray-800 flex flex-col bg-gray-950
                  transition-all duration-200 min-h-0 h-full overflow-hidden
                  ${mobile ? "w-[86vw] max-w-[320px] shadow-2xl" : effectiveCollapsed ? "w-10" : "w-56"}`}
    >
      {/* Header */}
      <div className={`flex items-center border-b border-gray-800 min-h-[57px]
                       ${effectiveCollapsed ? "justify-center px-0 py-4" : "px-3 py-3 gap-2"}`}>
        {!effectiveCollapsed && (
          <button type="button" onClick={onNew} disabled={disableNew}
            className="flex-1 flex items-center gap-2 px-3 py-2 rounded-xl border border-gray-700
                       text-gray-400 text-sm hover:border-indigo-500 hover:text-white transition-colors
                       disabled:opacity-40 disabled:cursor-not-allowed">
            <Plus size={14} /> 新建对话
          </button>
        )}
        <button type="button"
          onClick={mobile ? onClose : toggle}
          className="p-1.5 rounded-lg text-gray-500 hover:text-white hover:bg-gray-800 transition-colors flex-shrink-0">
          {mobile ? <X size={14} /> : effectiveCollapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
        </button>
      </div>

      {effectiveCollapsed && !mobile && (
        <div className="flex justify-center py-2 border-b border-gray-800">
          <button type="button" onClick={onNew} disabled={disableNew}
            className="p-1.5 rounded-lg text-gray-500 hover:text-white hover:bg-gray-800 transition-colors disabled:opacity-40">
            <Plus size={14} />
          </button>
        </div>
      )}

      {!effectiveCollapsed && (
        <>
          {/* Search */}
          <div className="px-2 py-2 border-b border-gray-800">
            <div className="relative">
              <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-600 pointer-events-none" />
              <input value={query} onChange={(e) => setQuery(e.target.value)}
                placeholder="搜索对话..."
                className="w-full pl-7 pr-6 py-1.5 bg-gray-900 border border-gray-800 rounded-lg
                           text-xs text-gray-300 outline-none focus:border-gray-600 placeholder-gray-600" />
              {query && (
                <button type="button" onClick={() => setQuery("")}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-600 hover:text-gray-300">
                  <X size={11} />
                </button>
              )}
            </div>
          </div>

          {/* Categories */}
          {categories.length > 0 && (
            <div className="px-2 py-1 border-b border-gray-800 flex flex-wrap gap-1">
              <button onClick={() => setActiveCat(null)}
                className={`px-2 py-0.5 rounded text-[10px] transition-colors ${!activeCat ? "bg-indigo-900/40 text-indigo-300" : "text-gray-500 hover:text-gray-300"}`}>
                全部
              </button>
              {categories.map((cat) => (
                <button key={cat.id} onClick={() => setActiveCat(cat.id === activeCat ? null : cat.id)}
                  className={`flex items-center gap-1 px-2 py-0.5 rounded text-[10px] transition-colors ${activeCat === cat.id ? "bg-indigo-900/40 text-indigo-300" : "text-gray-500 hover:text-gray-300"}`}>
                  <Folder size={9} style={{ color: cat.color }} />
                  {cat.name}
                  <span className="opacity-60">({cat.count})</span>
                </button>
              ))}
            </div>
          )}
        </>
      )}

      {/* Conversation list */}
      {!effectiveCollapsed ? (
        <div className="flex-1 overflow-auto px-2 py-2">
          {filtered.length === 0 ? (
            <div className="px-3 py-8 text-center text-xs text-gray-600">
              {query ? "无匹配对话" : "暂无对话记录"}
            </div>
          ) : (
            filtered.map((conv) => (
              <ConversationCard key={conv.id}
                conv={conv}
                active={activeId === conv.id}
                onSelect={() => onSelect(conv.id)}
                onDelete={() => onDelete(conv.id)}
                onPin={() => handlePin(conv.id)}
                onArchive={() => handleArchive(conv.id)}
                relatedTitle={conversations.find((c) => c.id === conv.branch_from_conversation_id)?.title}
              />
            ))
          )}
        </div>
      ) : (
        <div className="flex-1 overflow-auto py-2 flex flex-col items-center gap-1">
          {conversations.filter((c) => c.id && !c.is_archived).map((conv) => (
            <button key={conv.id} type="button" onClick={() => onSelect(conv.id)} title={conv.title}
              className={`p-1.5 rounded-lg transition-colors ${activeId === conv.id ? "bg-gray-800 text-white" : "text-gray-600 hover:text-white hover:bg-gray-800"}`}>
              <Folder size={14} />
            </button>
          ))}
        </div>
      )}
    </aside>
  );
}
