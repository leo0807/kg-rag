"use client";

import { GitBranch, MessageSquare, Pin, Archive, Trash2, Tag } from "lucide-react";
import type { Conversation } from "./types";

interface Props {
  conv: Conversation;
  active: boolean;
  onSelect: () => void;
  onDelete: () => void;
  onPin?: () => void;
  onArchive?: () => void;
  relatedTitle?: string;
}

export function ConversationCard({
  conv, active, onSelect, onDelete, onPin, onArchive, relatedTitle,
}: Props) {
  return (
    <div
      className={`group relative mb-0.5 rounded-xl transition-colors ${
        active
          ? "bg-gray-800 text-white"
          : "text-gray-400 hover:bg-gray-900 hover:text-gray-300"
      }`}
    >
      <button
        type="button"
        onClick={onSelect}
        className="flex w-full items-start gap-2 px-3 py-2.5 pr-8 text-left"
      >
        {conv.is_pinned ? (
          <Pin size={13} className="shrink-0 mt-0.5 text-amber-400" />
        ) : (
          <MessageSquare size={13} className="shrink-0 mt-0.5" />
        )}
        <div className="flex-1 min-w-0">
          <div className="text-xs leading-relaxed line-clamp-2">{conv.title}</div>
          {conv.branch_from_conversation_id ? (
            <div className="mt-0.5 flex items-center gap-1 text-[10px] text-gray-500">
              <GitBranch size={9} />
              <span className="truncate">
                派生自 {relatedTitle ?? "已删除对话"}
                {conv.branch_from_message_index != null &&
                  ` 第 ${conv.branch_from_message_index + 1} 条`}
              </span>
            </div>
          ) : (
            <div className="text-[10px] text-gray-600 mt-0.5">
              {conv.messages.length / 2} 轮
              {conv.tags && conv.tags.length > 0 && (
                <span className="ml-1 inline-flex items-center gap-0.5">
                  <Tag size={8} />
                  {conv.tags.slice(0, 2).join(" ")}
                </span>
              )}
            </div>
          )}
        </div>
      </button>

      {/* Action buttons */}
      <div className="absolute right-1.5 top-1/2 -translate-y-1/2 hidden group-hover:flex items-center gap-0.5">
        {onPin && (
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); onPin(); }}
            className={`p-0.5 rounded transition-colors ${conv.is_pinned ? "text-amber-400" : "text-gray-600 hover:text-amber-400"}`}
            title={conv.is_pinned ? "取消置顶" : "置顶"}
          >
            <Pin size={11} />
          </button>
        )}
        {onArchive && (
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); onArchive(); }}
            className="p-0.5 rounded text-gray-600 hover:text-blue-400 transition-colors"
            title="归档"
          >
            <Archive size={11} />
          </button>
        )}
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onDelete(); }}
          className="p-0.5 rounded text-gray-600 hover:text-red-400 transition-colors"
          title="删除"
        >
          <Trash2 size={11} />
        </button>
      </div>
    </div>
  );
}
