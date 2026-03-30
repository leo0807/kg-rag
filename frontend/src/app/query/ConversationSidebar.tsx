"use client";
import { Plus, Trash2, MessageSquare } from "lucide-react";
import { Conversation } from "./types";

interface Props {
    conversations: Conversation[];
    activeId: string | null;
    onSelect: (id: string) => void;
    onDelete: (id: string) => void;
    onNew: () => void;
}

export default function ConversationSidebar({
    conversations, activeId, onSelect, onDelete, onNew,
}: Props) {
    return (
        <aside className="w-56 shrink-0 border-r border-gray-800 flex flex-col bg-gray-950">
            <div className="px-3 py-4 border-b border-gray-800">
                <button onClick={onNew}
                    className="w-full flex items-center gap-2 px-3 py-2 rounded-xl
                     border border-gray-700 text-gray-400 text-sm
                     hover:border-indigo-500 hover:text-white transition-colors">
                    <Plus size={14} />
                    新建对话
                </button>
            </div>

            <div className="flex-1 overflow-auto px-2 py-2">
                {conversations.length === 0 ? (
                    <div className="px-3 py-8 text-center text-xs text-gray-600">
                        暂无对话记录
                    </div>
                ) : conversations.filter(c => c.id).map(conv => (
                    <div key={conv.id}
                        className={`group flex items-start gap-2 px-3 py-2.5 rounded-xl mb-0.5
                        cursor-pointer transition-colors ${activeId === conv.id
                                ? "bg-gray-800 text-white"
                                : "text-gray-400 hover:bg-gray-900 hover:text-gray-300"
                            }`}
                        onClick={() => onSelect(conv.id)}>
                        <MessageSquare size={14} className="shrink-0 mt-0.5" />
                        <div className="flex-1 min-w-0">
                            <div className="text-xs leading-relaxed line-clamp-2">
                                {conv.title}
                            </div>
                            <div className="text-xs text-gray-600 mt-0.5">
                                {conv.messages.length / 2} 轮对话
                            </div>
                        </div>
                        <button
                            onClick={e => { e.stopPropagation(); onDelete(conv.id); }}
                            className="opacity-0 group-hover:opacity-100 shrink-0
                         p-0.5 hover:text-red-400 transition-all">
                            <Trash2 size={12} />
                        </button>
                    </div>
                ))}
            </div>
        </aside>
    );
}