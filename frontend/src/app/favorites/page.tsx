"use client";

import { useState } from "react";
import { Search, Star } from "lucide-react";
import { useFavorites } from "./useFavorites";
import { FavoriteCard } from "./FavoriteCard";
import { EmptyWorkspace } from "./EmptyWorkspace";

type TabType = "all" | "section" | "document" | "query";

const TABS: { key: TabType; label: string }[] = [
  { key: "all",      label: "全部" },
  { key: "section",  label: "章节" },
  { key: "document", label: "文档" },
  { key: "query",    label: "常用问题" },
];

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
      <div className="max-w-3xl mx-auto px-4 py-8 sm:px-6 sm:py-10">
        <div className="flex items-center gap-3 mb-8">
          <Star size={20} className="text-amber-400 fill-amber-400" />
          <h1 className="text-xl font-semibold text-gray-100">收藏夹</h1>
          <span className="ml-auto text-xs text-gray-600">{favorites.length} 条收藏</span>
        </div>

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

        <div className="flex gap-1 mb-6 bg-gray-900 border border-gray-800 rounded-xl p-1">
          {TABS.map(t => {
            const count = t.key === "all"
              ? favorites.length
              : favorites.filter(f => f.type === t.key).length;
            return (
              <button key={t.key} onClick={() => setTab(t.key)}
                className={`flex-1 py-1.5 text-xs rounded-lg transition-colors ${
                  tab === t.key ? "bg-gray-800 text-gray-100 font-medium" : "text-gray-600 hover:text-gray-400"
                }`}>
                {t.label}
                {count > 0 && <span className="ml-1 text-gray-600">({count})</span>}
              </button>
            );
          })}
        </div>

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
          <div className="space-y-3 stagger-children">
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
