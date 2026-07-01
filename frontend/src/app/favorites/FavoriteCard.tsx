"use client";

import Link from "next/link";
import { useState } from "react";
import { BookOpen, Check, Edit3, FileText, MessageSquare, Trash2, X } from "lucide-react";
import type { FavoriteItem } from "./useFavorites";

function FavoriteIcon({ type }: { type: string }) {
  if (type === "section")  return <BookOpen   size={14} className="text-indigo-400 shrink-0" />;
  if (type === "document") return <FileText    size={14} className="text-green-400 shrink-0" />;
  return                          <MessageSquare size={14} className="text-amber-400 shrink-0" />;
}

interface Props {
  item:        FavoriteItem;
  onRemove:    (id: string) => void;
  onPatchNote: (id: string, note: string | null) => Promise<boolean>;
}

export function FavoriteCard({ item, onRemove, onPatchNote }: Props) {
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

          {editing ? (
            <div className="mt-2 flex items-start gap-2">
              <textarea
                value={draft}
                onChange={e => setDraft(e.target.value)}
                rows={2}
                placeholder="添加备注..."
                className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-xs text-gray-300 resize-none outline-none focus:border-indigo-500"
                autoFocus
              />
              <div className="flex flex-col gap-1">
                <button onClick={saveNote} disabled={saving}
                  className="p-1.5 bg-indigo-600 hover:bg-indigo-500 rounded-lg disabled:opacity-50">
                  <Check size={11} className="text-white" />
                </button>
                <button onClick={() => { setEditing(false); setDraft(item.note ?? ""); }}
                  className="p-1.5 bg-gray-700 hover:bg-gray-600 rounded-lg">
                  <X size={11} className="text-gray-300" />
                </button>
              </div>
            </div>
          ) : (
            <div onClick={() => setEditing(true)}
              className="mt-2 text-xs text-gray-600 hover:text-gray-400 cursor-pointer min-h-[1.25rem] italic">
              {item.note ?? <span className="flex items-center gap-1"><Edit3 size={10} /> 添加备注</span>}
            </div>
          )}
        </div>

        <button onClick={() => onRemove(item.id)} title="删除收藏"
          className="shrink-0 p-1.5 text-gray-700 hover:text-red-400 hover:bg-red-950/30 rounded-lg transition-colors">
          <Trash2 size={13} />
        </button>
      </div>
    </div>
  );
}
