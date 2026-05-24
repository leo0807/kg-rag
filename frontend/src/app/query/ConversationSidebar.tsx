"use client";

import {
  ChevronLeft,
  ChevronRight,
  GitBranch,
  MessageSquare,
  Plus,
  Search,
  Trash2,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";
import type { Conversation } from "./types";

interface Props {
  conversations: Conversation[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  onNew: () => void;
  disableNew?: boolean;
  mobile?: boolean;
  onClose?: () => void;
}

const STORAGE_KEY = "conv_sidebar_collapsed";

export default function ConversationSidebar({
  conversations,
  activeId,
  onSelect,
  onDelete,
  onNew,
  disableNew = false,
  mobile = false,
  onClose,
}: Props) {
  const [collapsed, setCollapsed] = useState(false);
  const [query, setQuery] = useState("");
  const effectiveCollapsed = mobile ? false : collapsed;

  useEffect(() => {
    if (localStorage.getItem(STORAGE_KEY) === "1") setCollapsed(true);
  }, []);

  function toggle() {
    setCollapsed((v) => {
      const next = !v;
      localStorage.setItem(STORAGE_KEY, next ? "1" : "0");
      return next;
    });
  }

  return (
    <aside
      className={`shrink-0 border-r border-gray-800 flex flex-col bg-gray-950
                           transition-all duration-200 min-h-0 h-full overflow-hidden
                           ${mobile ? "w-[86vw] max-w-[320px] shadow-2xl" : effectiveCollapsed ? "w-10" : "w-56"}`}
    >
      {/* 折叠按钮 */}
      <div
        className={`flex items-center border-b border-gray-800 min-h-[57px]
                             ${effectiveCollapsed ? "justify-center px-0 py-4" : "px-3 py-3 gap-2"}`}
      >
        {!effectiveCollapsed && (
          <button
            type="button"
            onClick={onNew}
            disabled={disableNew}
            className="flex-1 flex items-center gap-2 px-3 py-2 rounded-xl
                         border border-gray-700 text-gray-400 text-sm
                         hover:border-indigo-500 hover:text-white transition-colors
                         disabled:opacity-40 disabled:cursor-not-allowed
                         disabled:hover:border-gray-700 disabled:hover:text-gray-400"
          >
            <Plus size={14} />
            新建对话
          </button>
        )}
        {mobile ? (
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-gray-500 hover:text-white hover:bg-gray-800 transition-colors flex-shrink-0"
            title="关闭会话列表"
          >
            <X size={14} />
          </button>
        ) : (
          <button
            type="button"
            onClick={toggle}
            className="p-1.5 rounded-lg text-gray-500 hover:text-white hover:bg-gray-800 transition-colors flex-shrink-0"
            title={effectiveCollapsed ? "展开历史" : "折叠历史"}
          >
            {effectiveCollapsed ? (
              <ChevronRight size={14} />
            ) : (
              <ChevronLeft size={14} />
            )}
          </button>
        )}
      </div>

      {/* 折叠时显示新建按钮图标 */}
      {effectiveCollapsed && !mobile && (
        <div className="flex justify-center py-2 border-b border-gray-800">
          <button
            type="button"
            onClick={onNew}
            disabled={disableNew}
            className="p-1.5 rounded-lg text-gray-500 hover:text-white hover:bg-gray-800 transition-colors
                                   disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-transparent"
            title={disableNew ? "请先发送消息后再新建对话" : "新建对话"}
          >
            <Plus size={14} />
          </button>
        </div>
      )}

      {/* 搜索框 */}
      {!effectiveCollapsed && (
        <div className="px-2 py-2 border-b border-gray-800">
          <div className="relative">
            <Search
              size={12}
              className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-600 pointer-events-none"
            />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="搜索对话..."
              className="w-full pl-7 pr-6 py-1.5 bg-gray-900 border border-gray-800
                                       rounded-lg text-xs text-gray-300 outline-none
                                       focus:border-gray-600 placeholder-gray-600 transition-colors"
            />
            {query && (
              <button
                type="button"
                onClick={() => setQuery("")}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-600 hover:text-gray-300 transition-colors"
              >
                <X size={11} />
              </button>
            )}
          </div>
        </div>
      )}

      {/* 对话列表 */}
      {!collapsed && (
        <div className="flex-1 overflow-auto px-2 py-2">
          {(() => {
            const filtered = conversations
              .filter((c) => c.id)
              .filter(
                (c) =>
                  !query || c.title.toLowerCase().includes(query.toLowerCase()),
              );
            if (filtered.length === 0)
              return (
                <div className="px-3 py-8 text-center text-xs text-gray-600">
                  {query ? "无匹配对话" : "暂无对话记录"}
                </div>
              );
            return filtered.map((conv) => (
              <div
                key={conv.id}
                className={`group relative mb-0.5 rounded-xl transition-colors ${
                  activeId === conv.id
                    ? "bg-gray-800 text-white"
                    : "text-gray-400 hover:bg-gray-900 hover:text-gray-300"
                }`}
              >
                <button
                  type="button"
                  onClick={() => onSelect(conv.id)}
                  className="flex w-full items-start gap-2 px-3 py-2.5 pr-8 text-left"
                >
                  <MessageSquare size={14} className="shrink-0 mt-0.5" />
                  <div className="flex-1 min-w-0">
                    <div className="text-xs leading-relaxed line-clamp-2">
                      {conv.title}
                    </div>
                    {conv.branch_from_conversation_id ? (
                      <div className="mt-0.5 flex items-center gap-1 text-[10px] text-gray-500">
                        <GitBranch size={10} />
                        <span className="truncate">
                          派生自{" "}
                          {conversations.find(
                            (c) => c.id === conv.branch_from_conversation_id,
                          )?.title ?? "已删除对话"}
                          {conv.branch_from_message_index != null &&
                            ` 第 ${conv.branch_from_message_index + 1} 条`}
                        </span>
                      </div>
                    ) : (
                      <div className="text-xs text-gray-600 mt-0.5">
                        {conv.messages.length / 2} 轮对话
                      </div>
                    )}
                  </div>
                </button>
                <button
                  type="button"
                  onClick={() => onDelete(conv.id)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 opacity-0 shrink-0 p-0.5 transition-all hover:text-red-400 group-hover:opacity-100"
                >
                  <Trash2 size={12} />
                </button>
              </div>
            ));
          })()}
        </div>
      )}

      {/* 折叠时显示对话图标列表 */}
      {effectiveCollapsed && !mobile && (
        <div className="flex-1 overflow-auto py-2 flex flex-col items-center gap-1">
          {conversations
            .filter((c) => c.id)
            .map((conv) => (
              <button
                type="button"
                key={conv.id}
                onClick={() => onSelect(conv.id)}
                title={conv.title}
                className={`p-1.5 rounded-lg transition-colors ${
                  activeId === conv.id
                    ? "bg-gray-800 text-white"
                    : "text-gray-600 hover:text-white hover:bg-gray-800"
                }`}
              >
                <MessageSquare size={14} />
              </button>
            ))}
        </div>
      )}
    </aside>
  );
}
