"use client";
import { Trash2, Plus } from "lucide-react";

interface Session {
    id: string;
    question: string;
    answer: string;
    sources: any[];
    timestamp: number;
}

interface Props {
    sessions: Session[];
    activeSession: string | null;
    onSelect: (session: Session) => void;
    onDelete: (id: string) => void;
    onNew: () => void;
}

export default function SessionList({ sessions, activeSession, onSelect, onDelete, onNew }: Props) {
    return (
        <aside className="w-52 shrink-0 border-r border-gray-800 flex flex-col">
            <div className="px-4 py-3 border-b border-gray-800 flex items-center justify-between">
                <div className="text-xs text-gray-500 uppercase tracking-wider">历史记录</div>
                <button onClick={onNew}
                    className="inline-flex items-center gap-1 px-2 py-1 bg-indigo-600
                     text-white text-xs rounded hover:bg-indigo-500">
                    <Plus size={12} /> 新建
                </button>
            </div>
            <div className="flex-1 overflow-auto px-2 py-2">
                {sessions.length === 0 ? (
                    <div className="px-2 py-3 text-xs text-gray-600">暂无记录</div>
                ) : sessions.map(session => (
                    <div key={session.id}
                        className={`group flex items-start gap-1 px-2 py-2 rounded-lg mb-0.5
                        cursor-pointer transition-colors ${activeSession === session.id ? "bg-gray-800" : "hover:bg-gray-900"
                            }`}
                        onClick={() => onSelect(session)}>
                        <span className="flex-1 text-xs text-gray-400 leading-relaxed line-clamp-2">
                            {session.question}
                        </span>
                        <button
                            onClick={e => { e.stopPropagation(); onDelete(session.id); }}
                            className="opacity-0 group-hover:opacity-100 flex-shrink-0
                         p-0.5 text-gray-600 hover:text-red-400 transition-all">
                            <Trash2 size={12} />
                        </button>
                    </div>
                ))}
            </div>
        </aside>
    );
}