"use client";

import { useEffect, useState } from "react";
import { Languages, Plus, Trash2 } from "lucide-react";
import { fetchApi } from "@/lib/api";

interface Entry {
  term: string;
  synonyms: string[];
}

export default function SynonymsPage() {
  const [entries, setEntries] = useState<Entry[]>([]);
  const [total, setTotal] = useState(0);
  const [newTerm, setNewTerm] = useState("");
  const [newSyns, setNewSyns] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      const d = await fetchApi<{ total: number; entries: Entry[] }>("/api/admin/synonyms");
      setEntries(d.entries);
      setTotal(d.total);
    } catch { setError("加载失败"); }
  }

  useEffect(() => { void load(); }, []);

  async function handleAdd() {
    const term = newTerm.trim();
    const synonyms = newSyns.split(/[,，]+/).map((s) => s.trim()).filter(Boolean);
    if (!term || synonyms.length === 0) { setError("词条和同义词不能为空"); return; }
    setSaving(true); setError(null);
    try {
      await fetchApi("/api/admin/synonyms", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ term, synonyms }),
      });
      setNewTerm(""); setNewSyns("");
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "保存失败");
    } finally { setSaving(false); }
  }

  async function handleDelete(term: string) {
    try {
      await fetchApi(`/api/admin/synonyms/${encodeURIComponent(term)}`, { method: "DELETE" });
      await load();
    } catch { setError("删除失败"); }
  }

  return (
    <div className="flex-1 overflow-auto bg-gray-950 p-6 space-y-6">
      <div className="rounded-3xl border border-gray-800 bg-[radial-gradient(circle_at_top_left,rgba(139,92,246,0.15),transparent_40%),#111827] p-6">
        <h1 className="text-2xl font-semibold text-white flex items-center gap-2">
          <Languages size={22} className="text-violet-400" />
          同义词词典
        </h1>
        <p className="mt-1 text-sm text-gray-400">管理查询扩展词典，新增词条立即生效（无需重启）。{total} 个词条。</p>
      </div>

      <div className="rounded-3xl border border-gray-800 bg-gray-900 p-5">
        <div className="text-white font-medium mb-3">新增 / 覆盖词条</div>
        {error && <div className="mb-3 rounded-lg bg-red-950/50 border border-red-800/60 px-3 py-2 text-sm text-red-300">{error}</div>}
        <div className="flex gap-3 flex-wrap">
          <input
            value={newTerm} onChange={(e) => setNewTerm(e.target.value)}
            placeholder="词条（如：钛合金）"
            className="w-44 rounded-xl border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white placeholder-gray-500 outline-none focus:border-violet-500"
          />
          <input
            value={newSyns} onChange={(e) => setNewSyns(e.target.value)}
            placeholder="同义词（逗号分隔，如：TC4, Ti-6Al-4V）"
            className="flex-1 min-w-48 rounded-xl border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white placeholder-gray-500 outline-none focus:border-violet-500"
          />
          <button
            type="button" onClick={handleAdd} disabled={saving}
            className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium disabled:opacity-50 transition-colors"
          >
            <Plus size={14} /> 保存
          </button>
        </div>
      </div>

      <div className="rounded-3xl border border-gray-800 bg-gray-900 p-5">
        <div className="overflow-auto">
          <table className="w-full text-sm">
            <thead className="text-gray-400 text-left">
              <tr>
                <th className="pb-3 pr-6 w-40">词条</th>
                <th className="pb-3 pr-4">同义词</th>
                <th className="pb-3 w-12" />
              </tr>
            </thead>
            <tbody className="text-gray-300">
              {entries.map((e) => (
                <tr key={e.term} className="border-t border-gray-800 hover:bg-gray-800/30">
                  <td className="py-2.5 pr-6 font-medium text-white">{e.term}</td>
                  <td className="py-2.5 pr-4">
                    <div className="flex flex-wrap gap-1">
                      {e.synonyms.map((s) => (
                        <span key={s} className="rounded-md bg-violet-950/50 border border-violet-800/40 px-1.5 py-0.5 text-[11px] text-violet-300">{s}</span>
                      ))}
                    </div>
                  </td>
                  <td className="py-2.5 text-right">
                    <button type="button" onClick={() => handleDelete(e.term)}
                      className="p-1.5 rounded-lg text-gray-600 hover:text-red-400 hover:bg-red-950/30 transition-colors" title="删除">
                      <Trash2 size={13} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
