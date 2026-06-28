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
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 hover:border-gray-700 transition-colors tech-card">
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

const EXAMPLE_ITEMS = [
    {
        type: "section", icon: BookOpen, color: "text-indigo-400",
        title: "4.3.2 铆接工艺参数要求",
        sub: "CPS-HY-0412 · 第 4 章",
        note: "常用参数，快速对照",
    },
    {
        type: "document", icon: FileText, color: "text-green-400",
        title: "航空工艺规范 · 复合材料铺层标准",
        sub: "CPS-CM-2201",
        note: "当前项目主要规范",
    },
    {
        type: "query", icon: MessageSquare, color: "text-amber-400",
        title: "复合材料固化温度范围是多少？",
        sub: "常用问题",
        note: "",
    },
];

function EmptyWorkspace() {
    return (
        <div style={{ animation: "slide-up-fade 0.6s ease both" }}>
            {/* Hint */}
            <div className="text-center mb-6">
                <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-amber-500/10 border border-amber-500/20 mb-3"
                    style={{ animation: "glow-pulse 3s ease-in-out infinite" }}>
                    <Star size={20} className="text-amber-400 fill-amber-400/30" />
                </div>
                <p className="text-sm font-medium text-gray-300">工作区还是空的</p>
                <p className="text-xs text-gray-600 mt-1">在问答页面或文档库中点击 ★ 即可收藏到这里</p>
            </div>

            {/* Example cards */}
            <div className="text-xs text-gray-600 uppercase tracking-wider mb-3 px-1">示例收藏（仅预览）</div>
            <div className="space-y-2.5 stagger-children pointer-events-none select-none">
                {EXAMPLE_ITEMS.map((ex, i) => (
                    <div key={i} className="relative bg-gray-900/60 border border-gray-800/60 rounded-xl p-4 opacity-60">
                        <span className="absolute top-3 right-3 text-[9px] px-1.5 py-0.5 bg-gray-800 text-gray-600 rounded-full border border-gray-700">示例</span>
                        <div className="flex items-start gap-3">
                            <ex.icon size={14} className={`${ex.color} shrink-0 mt-0.5`} />
                            <div className="flex-1 min-w-0">
                                <div className="text-sm font-medium text-gray-300 truncate">{ex.title}</div>
                                <div className="text-xs text-gray-600 mt-0.5 font-mono">{ex.sub}</div>
                                {ex.note && (
                                    <div className="text-xs text-gray-600 italic mt-1">{ex.note}</div>
                                )}
                            </div>
                        </div>
                    </div>
                ))}
            </div>

            {/* CTA */}
            <div className="flex gap-3 mt-6">
                <Link href="/query"
                    className="flex-1 text-center py-2 text-xs bg-indigo-600/20 border border-indigo-600/30 text-indigo-400 rounded-lg hover:bg-indigo-600/30 transition-colors">
                    去问答页面
                </Link>
                <Link href="/library"
                    className="flex-1 text-center py-2 text-xs bg-gray-800/60 border border-gray-700/60 text-gray-400 rounded-lg hover:bg-gray-800 transition-colors">
                    去文档库
                </Link>
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
                    search ? (
                        <div className="text-center py-16 text-gray-700">
                            <Star size={28} className="mx-auto mb-3 opacity-30" />
                            <div className="text-sm">没有匹配的收藏</div>
                        </div>
                    ) : (
                        <EmptyWorkspace />
                    )
                ) : (
                    <div className="space-y-3 stagger-left">
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
