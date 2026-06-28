"use client";

import { Download, Edit3, Plus, Search, Tag, Trash2, X } from "lucide-react";
import { useEffect, useState } from "react";
import { fetchApi, getApiBaseUrl } from "@/lib/api";

interface Note {
  id: string;
  title: string;
  content: string;
  tags: string[];
  visibility: string;
  related_chunk_id?: string;
  created_at: string;
  updated_at: string;
}

export default function NotesPage() {
  const [notes, setNotes] = useState<Note[]>([]);
  const [q, setQ] = useState("");
  const [editing, setEditing] = useState<Note | null>(null);
  const [creating, setCreating] = useState(false);
  const [draft, setDraft] = useState({ title: "", content: "", tags: "" });

  async function load() {
    const data = await fetchApi<Note[]>(`/api/notes${q ? `?q=${encodeURIComponent(q)}` : ""}`);
    setNotes(data);
  }

  useEffect(() => { load(); }, [q]); // eslint-disable-line react-hooks/exhaustive-deps

  async function save() {
    const tags = draft.tags.split(/[,，\s]+/).map((t) => t.trim()).filter(Boolean);
    if (editing) {
      await fetchApi(`/api/notes/${editing.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: draft.title, content: draft.content, tags }),
      });
    } else {
      await fetchApi("/api/notes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: draft.title, content: draft.content, tags }),
      });
    }
    setEditing(null);
    setCreating(false);
    setDraft({ title: "", content: "", tags: "" });
    load();
  }

  async function remove(id: string) {
    if (!confirm("确认删除该笔记？")) return;
    await fetchApi(`/api/notes/${id}`, { method: "DELETE" });
    load();
  }

  async function exportNote(id: string) {
    const token = localStorage.getItem("token");
    window.open(`${getApiBaseUrl()}/api/notes/${id}/export?token=${token}`, "_blank");
  }

  function openEdit(note: Note) {
    setEditing(note);
    setDraft({ title: note.title, content: note.content, tags: note.tags.join(", ") });
  }

  const isEditorOpen = editing || creating;

  return (
    <div className="flex-1 flex overflow-hidden bg-gray-950">
      {/* List */}
      <div className={`flex flex-col ${isEditorOpen ? "w-72 shrink-0" : "flex-1"} border-r border-gray-800`}>
        <div className="flex items-center gap-2 px-4 py-3 border-b border-gray-800">
          <h1 className="text-sm font-semibold text-gray-200 flex-1">我的笔记</h1>
          <button onClick={() => { setCreating(true); setEditing(null); setDraft({ title: "", content: "", tags: "" }); }}
            className="p-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white transition-colors">
            <Plus size={13} />
          </button>
        </div>

        <div className="px-3 py-2 border-b border-gray-800">
          <div className="relative">
            <Search size={11} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-600 pointer-events-none" />
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="搜索笔记…"
              className="w-full pl-7 pr-3 py-1.5 bg-gray-900 border border-gray-800 rounded-lg
                         text-xs text-gray-300 outline-none focus:border-gray-600 placeholder-gray-600" />
          </div>
        </div>

        <div className="flex-1 overflow-auto px-2 py-2 space-y-1 stagger-children">
          {notes.length === 0 && (
            <p className="text-xs text-gray-600 text-center py-8">暂无笔记</p>
          )}
          {notes.map((note) => (
            <div key={note.id}
              onClick={() => openEdit(note)}
              className={`group p-3 rounded-xl border cursor-pointer transition-colors tech-card ${
                editing?.id === note.id
                  ? "border-indigo-700 bg-indigo-900/20"
                  : "border-gray-800 hover:border-gray-700 hover:bg-gray-900/50"
              }`}>
              <div className="flex items-start justify-between gap-2">
                <p className="text-xs font-medium text-gray-200 truncate">{note.title || "无标题"}</p>
                <div className="flex gap-1 opacity-0 group-hover:opacity-100 shrink-0">
                  <button onClick={(e) => { e.stopPropagation(); exportNote(note.id); }}
                    className="p-0.5 text-gray-600 hover:text-blue-400 transition-colors"><Download size={11} /></button>
                  <button onClick={(e) => { e.stopPropagation(); remove(note.id); }}
                    className="p-0.5 text-gray-600 hover:text-red-400 transition-colors"><Trash2 size={11} /></button>
                </div>
              </div>
              {note.content && (
                <p className="text-[10px] text-gray-600 mt-1 line-clamp-2">{note.content}</p>
              )}
              {note.tags.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-1.5">
                  {note.tags.map((t) => (
                    <span key={t} className="inline-flex items-center gap-0.5 text-[9px] px-1.5 py-0.5
                                             bg-gray-800 text-gray-500 rounded">
                      <Tag size={8} />{t}
                    </span>
                  ))}
                </div>
              )}
              <p className="text-[9px] text-gray-700 mt-1">{new Date(note.updated_at).toLocaleDateString("zh-CN")}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Editor */}
      {isEditorOpen && (
        <div className="flex-1 flex flex-col">
          <div className="flex items-center gap-3 px-4 py-3 border-b border-gray-800">
            <input value={draft.title} onChange={(e) => setDraft((d) => ({ ...d, title: e.target.value }))}
              placeholder="笔记标题"
              className="flex-1 bg-transparent text-sm font-medium text-gray-100 outline-none placeholder-gray-600" />
            <button onClick={() => { setEditing(null); setCreating(false); }}
              className="text-gray-600 hover:text-gray-300"><X size={14} /></button>
          </div>

          <textarea value={draft.content}
            onChange={(e) => setDraft((d) => ({ ...d, content: e.target.value }))}
            placeholder="在此编写笔记内容（支持 Markdown）…"
            className="flex-1 bg-transparent text-sm text-gray-300 leading-relaxed px-4 py-3 resize-none
                       outline-none font-mono placeholder-gray-700" />

          <div className="px-4 py-3 border-t border-gray-800 flex items-center gap-3">
            <Tag size={11} className="text-gray-600 shrink-0" />
            <input value={draft.tags} onChange={(e) => setDraft((d) => ({ ...d, tags: e.target.value }))}
              placeholder="标签（逗号分隔）"
              className="flex-1 bg-transparent text-xs text-gray-400 outline-none placeholder-gray-700" />
            <button onClick={save} disabled={!draft.title.trim()}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500
                         disabled:opacity-40 text-white text-xs rounded-lg transition-colors">
              <Edit3 size={11} /> {editing ? "保存" : "创建"}
            </button>
          </div>
        </div>
      )}

      {!isEditorOpen && notes.length === 0 && (
        <div className="flex-1 flex items-center justify-center">
          <p className="text-xs text-gray-600">点击右上角 + 新建笔记</p>
        </div>
      )}
    </div>
  );
}
