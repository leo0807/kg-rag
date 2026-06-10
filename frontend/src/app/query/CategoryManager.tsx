"use client";

import { Folder, Plus, Trash2, X } from "lucide-react";
import { useState } from "react";
import { fetchApi } from "@/lib/api";
import type { ConversationCategory } from "./types";

const COLORS = ["#6366f1","#10b981","#f59e0b","#ef4444","#8b5cf6","#06b6d4","#ec4899","#84cc16"];

interface Props {
  categories: ConversationCategory[];
  onClose: () => void;
  onRefresh: () => void;
}

export function CategoryManager({ categories, onClose, onRefresh }: Props) {
  const [name, setName] = useState("");
  const [color, setColor] = useState(COLORS[0]);
  const [saving, setSaving] = useState(false);

  async function create() {
    if (!name.trim()) return;
    setSaving(true);
    try {
      await fetchApi("/api/conversations/categories", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name.trim(), color }),
      });
      setName("");
      onRefresh();
    } finally {
      setSaving(false);
    }
  }

  async function remove(id: string) {
    if (!confirm("删除分类后，该分类下的对话将变为未分类，确认？")) return;
    await fetchApi(`/api/conversations/categories/${id}`, { method: "DELETE" });
    onRefresh();
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-gray-900 border border-gray-700 rounded-xl p-5 w-80 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-100">管理分类</h2>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-300"><X size={15} /></button>
        </div>

        {/* Existing categories */}
        <div className="space-y-1 max-h-48 overflow-auto">
          {categories.length === 0 && (
            <p className="text-xs text-gray-600 text-center py-3">暂无分类</p>
          )}
          {categories.map((cat) => (
            <div key={cat.id}
              className="flex items-center gap-2 px-3 py-2 rounded-lg bg-gray-800">
              <Folder size={13} style={{ color: cat.color }} />
              <span className="flex-1 text-xs text-gray-300">{cat.name}</span>
              <span className="text-[10px] text-gray-600">{cat.count}</span>
              <button onClick={() => remove(cat.id)}
                className="text-gray-600 hover:text-red-400 transition-colors">
                <Trash2 size={11} />
              </button>
            </div>
          ))}
        </div>

        {/* New category */}
        <div className="space-y-2 pt-2 border-t border-gray-800">
          <p className="text-xs text-gray-500">新建分类</p>
          <input value={name} onChange={(e) => setName(e.target.value)}
            placeholder="分类名称"
            onKeyDown={(e) => e.key === "Enter" && create()}
            className="w-full px-3 py-1.5 bg-gray-800 border border-gray-700 rounded-lg text-xs text-gray-200
                       outline-none focus:border-indigo-600 placeholder-gray-600" />
          <div className="flex gap-1.5 flex-wrap">
            {COLORS.map((c) => (
              <button key={c} onClick={() => setColor(c)}
                className={`w-5 h-5 rounded-full border-2 transition-all ${color === c ? "border-white scale-110" : "border-transparent"}`}
                style={{ background: c }} />
            ))}
          </div>
          <button onClick={create} disabled={!name.trim() || saving}
            className="w-full flex items-center justify-center gap-1.5 py-1.5 bg-indigo-600 hover:bg-indigo-500
                       disabled:opacity-40 text-white text-xs rounded-lg transition-colors">
            <Plus size={12} /> 创建
          </button>
        </div>
      </div>
    </div>
  );
}
