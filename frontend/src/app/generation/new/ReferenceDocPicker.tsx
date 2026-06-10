"use client";

import { fetchApi } from "@/lib/api";
import { Search, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

interface DocItem { name: string; title?: string }

interface Props {
  selected: string[];
  onChange: (ids: string[]) => void;
}

export function ReferenceDocPicker({ selected, onChange }: Props) {
  const [query, setQuery]   = useState("");
  const [results, setResults] = useState<DocItem[]>([]);
  const [loading, setLoading] = useState(false);

  const search = useCallback(async (q: string) => {
    if (!q.trim()) { setResults([]); return; }
    setLoading(true);
    try {
      const d = await fetchApi<{ results: DocItem[] }>(
        `/api/search?q=${encodeURIComponent(q)}&type=document&limit=10`
      );
      setResults(d.results ?? []);
    } catch { setResults([]); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    const t = setTimeout(() => search(query), 350);
    return () => clearTimeout(t);
  }, [query, search]);

  const toggle = (id: string) => {
    onChange(
      selected.includes(id) ? selected.filter(s => s !== id) : [...selected, id]
    );
  };

  return (
    <div className="space-y-3">
      {/* Selected chips */}
      {selected.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {selected.map(id => (
            <span key={id}
              className="flex items-center gap-1 px-2 py-0.5 bg-indigo-900/40 border border-indigo-800 rounded text-xs text-indigo-300">
              {id}
              <button type="button" onClick={() => toggle(id)}>
                <X size={10} />
              </button>
            </span>
          ))}
        </div>
      )}

      {/* Search box */}
      <div className="relative">
        <Search size={13} className="absolute left-2.5 top-2.5 text-gray-500" />
        <input
          type="text"
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="搜索 CPS 文档编号或名称…"
          className="w-full bg-gray-900 border border-gray-700 rounded-lg pl-8 pr-3 py-2 text-xs text-gray-200 placeholder-gray-600 focus:outline-none focus:border-indigo-600"
        />
      </div>

      {/* Results */}
      {loading && <div className="text-xs text-gray-500">搜索中…</div>}
      {results.length > 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded-lg divide-y divide-gray-800 max-h-48 overflow-auto">
          {results.map(r => (
            <button key={r.name} type="button"
              onClick={() => { toggle(r.name); setQuery(""); setResults([]); }}
              className={`w-full text-left px-3 py-2 text-xs hover:bg-gray-800 transition-colors ${
                selected.includes(r.name) ? "text-indigo-400" : "text-gray-300"
              }`}>
              <span className="font-mono">{r.name}</span>
              {r.title && <span className="ml-2 text-gray-500">{r.title}</span>}
              {selected.includes(r.name) && <span className="ml-2 text-indigo-600">✓ 已选</span>}
            </button>
          ))}
        </div>
      )}

      <p className="text-[10px] text-gray-600">
        已选 {selected.length} 份参考文档。支持手动输入文档编号后按 Enter。
      </p>
    </div>
  );
}
