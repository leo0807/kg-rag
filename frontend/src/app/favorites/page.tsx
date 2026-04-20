"use client";

import { useState } from "react";
import Link from "next/link";
import { Star, Trash2, FileText, MessageSquare, BookOpen, Edit3, Check, X, Search } from "lucide-react";
import { useFavorites, FavoriteItem } from "./useFavorites";

type TabType = "all" | "section" | "document" | "query";

const TABS: { key: TabType; label: string }[] = [
    { key: "all",      label: "全部" },
    { key: "section",  label: "章节" },
    { key: "document", label: "文档" },
    { key: "query",    label: "常用问题" },
];

function FavoriteIcon({ type }: { type: string }) {
    if (type === "section")  return <BookOpen  size={14} className="text-indigo-400 shrink-0" />;
    if (type === "document") return <FileText   size={14} className="text-green-400 shrink-0" />;
    return <MessageSquare size={14} className="text-amber-400 shrink-0" />;
}

function FavoriteCard({
    item,
    onRemove,
    onPatchNote,
}: {
    item: FavoriteItem;
    onRemove: (id: string) => void;
    onPatchNote: (id: string, note: string | null) => Promise<boolean>;
}) {
    const [editing, setEditing] = useState(false);
    const [draft,   setDraft]   = useState(item.note ?? "");
    const [saving,  setSaving]  = useState(false);

    async function saveNote() {
        setSaving(true);
        const ok = await onPatchNote(item.id, draft.trim() || null);
        if (ok) setEditing(false);
        setSaving(false);
    }

    const href = item.type === "query"
        ? `/query?q=${encodeURIComponent(item.query_text ?? "")}`
        : item.type === "document"
        ? `/library/${item.doc_id}`
        : `/library/${item.doc_id}`;

    return (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 hover:border-gray-700 transition-colors">
            <div className="flex items-start gap-3">
                <FavoriteIcon type={item.type} />
                <div className="flex-1 min-w-0">
                    <Link href={href} className="text-sm font-medium text-gray-200 hover:text-indigo-400 transition-colors line-clamp-2">
                        {item.title}
                    </Link>
                    {item.type !== "query" && item.doc_id && (
                        <div className="text-xs text-gray-600 mt-0.5 font-mono">{item.doc_id}</div>
                    )}
                    <div className="text-xs text-gray-700 mt-1">
                        {new Date(item.created_at).toLocaleDateString("zh-CN")}
                    </div>

                    {/* 备注区域 */}
                    {editing ? (
                        <div className="mt-2 flex items-start gap-2">
                            <textarea
                                value={draft}
                                onChange={e => setDraft(e.target.value)}
                                rows={2}
                                placeholder="添加备注..."
                                className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2
                                           text-xs text-gray-300 resize-none outline-none focus:border-indigo-500"
                                autoFocus
                            />
                            <div className="flex flex-col gap-1">
                                <button
                                    onClick={saveNote}
                                    disabled={saving}
                                    className="p-1.5 bg-indigo-600 hover:bg-indigo-500 rounded-lg disabled:opacity-50"
                                >
                                    <Check size={11} className="text-white" />
                                </button>
                                <button
                                    onClick={() => { setEditing(false); setDraft(item.note ?? ""); }}
                                    className="p-1.5 bg-gray-700 hover:bg-gray-600 rounded-lg"
                                >
                                    <X size={11} className="text-gray-300" />
                                </button>
                            </div>
                        </div>
                    ) : (
                        <div
                            onClick={() => setEditing(true)}
                            className="mt-2 text-xs text-gray-600 hover:text-gray-400 cursor-pointer
                                       min-h-[1.25rem] italic"
                        >
                            {item.note ?? <span className="flex items-center gap-1"><Edit3 size={10} /> 添加备注</span>}
                        </div>
                    )}
                </div>

                <button
                    onClick={() => onRemove(item.id)}
                    title="删除收藏"
                    className="shrink-0 p-1.5 text-gray-700 hover:text-red-400 hover:bg-red-950/30
                               rounded-lg transition-colors"
                >
                    <Trash2 size={13} />
                </button>
            </div>
        </div>
    );
}

export default function FavoritesPage() {
    const { favorites, loaded, removeFavorite, patchNote } = useFavorites();
    const [tab,    setTab]    = useState<TabType>("all");
    const [search, setSearch] = useState("");

    const filtered = favorites.filter(f => {
        if (tab !== "all" && f.type !== tab) return false;
        if (!search.trim()) return true;
        const q = search.toLowerCase();
        return (
            f.title.toLowerCase().includes(q) ||
            (f.doc_id ?? "").toLowerCase().includes(q) ||
            (f.query_text ?? "").toLowerCase().includes(q) ||
            (f.note ?? "").toLowerCase().includes(q)
        );
    });

    return (
        <div className="min-h-screen bg-gray-950 text-white">
            <div className="max-w-3xl mx-auto px-6 py-10">
                {/* 页头 */}
                <div className="flex items-center gap-3 mb-8">
                    <Star size={20} className="text-amber-400 fill-amber-400" />
                    <h1 className="text-xl font-semibold text-gray-100">收藏夹</h1>
                    <span className="ml-auto text-xs text-gray-600">{favorites.length} 条收藏</span>
                </div>

                {/* 搜索 */}
                <div className="relative mb-5">
                    <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-600" />
                    <input
                        value={search}
                        onChange={e => setSearch(e.target.value)}
                        placeholder="搜索收藏..."
                        className="w-full bg-gray-900 border border-gray-800 rounded-xl pl-9 pr-4 py-2.5
                                   text-sm text-gray-300 placeholder-gray-600 outline-none focus:border-indigo-500"
                    />
                </div>

                {/* 标签页 */}
                <div className="flex gap-1 mb-6 bg-gray-900 border border-gray-800 rounded-xl p-1">
                    {TABS.map(t => {
                        const count = t.key === "all"
                            ? favorites.length
                            : favorites.filter(f => f.type === t.key).length;
                        return (
                            <button
                                key={t.key}
                                onClick={() => setTab(t.key)}
                                className={`flex-1 py-1.5 text-xs rounded-lg transition-colors ${
                                    tab === t.key
                                        ? "bg-gray-800 text-gray-100 font-medium"
                                        : "text-gray-600 hover:text-gray-400"
                                }`}
                            >
                                {t.label}
                                {count > 0 && (
                                    <span className="ml-1 text-gray-600">({count})</span>
                                )}
                            </button>
                        );
                    })}
                </div>

                {/* 列表 */}
                {!loaded ? (
                    <div className="space-y-3">
                        {[...Array(4)].map((_, i) => (
                            <div key={i} className="h-20 bg-gray-900 rounded-xl animate-pulse" />
                        ))}
                    </div>
                ) : filtered.length === 0 ? (
                    <div className="text-center py-20 text-gray-700">
                        <Star size={32} className="mx-auto mb-3 opacity-30" />
                        <div className="text-sm">
                            {search ? "没有匹配的收藏" : "还没有收藏，去问答页面或文档库添加吧"}
                        </div>
                    </div>
                ) : (
                    <div className="space-y-3">
                        {filtered.map(item => (
                            <FavoriteCard
                                key={item.id}
                                item={item}
                                onRemove={removeFavorite}
                                onPatchNote={patchNote}
                            />
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}
