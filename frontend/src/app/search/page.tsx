"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { Search, FileText, BookOpen, Tag, MessageSquare, Network } from "lucide-react";
import { fetchApi } from "@/lib/api";

interface SearchResult {
  chunk_id: string; doc_id: string; number: string; title: string;
  snippet: string; score: number; highlight?: Record<string, string[]>;
}
interface SuggestResult {
  documents: { doc_id: string; title: string; relevance: number }[];
  sections: { chunk_id: string; title: string; doc_id: string; relevance: number }[];
  entities: { name: string; type: string; mention_count: number }[];
  suggested_questions: string[];
}
interface EntityRels {
  doc_count: number; section_count: number;
  tools: string[]; materials: string[]; related_entities: string[];
}

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [suggest, setSuggest] = useState<SuggestResult | null>(null);
  const [showSuggest, setShowSuggest] = useState(false);
  const [selectedEntity, setSelectedEntity] = useState<string | null>(null);
  const [entityRels, setEntityRels] = useState<EntityRels | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!query.trim() || query.length < 2) { setSuggest(null); setShowSuggest(false); return; }
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      try {
        const data = await fetchApi<SuggestResult>(`/api/search/suggest?q=${encodeURIComponent(query)}&limit=5`);
        setSuggest(data);
        setShowSuggest(true);
      } catch { /* ignore */ }
    }, 300);
  }, [query]);

  async function handleSearch(q = query) {
    if (!q.trim()) return;
    setShowSuggest(false);
    setLoading(true);
    try {
      const res = await fetch(`/api/search?q=${encodeURIComponent(q)}&top_k=20`);
      const data = await res.json();
      setResults(data.results);
      setTotal(data.total);
    } finally { setLoading(false); }
  }

  async function handleEntityClick(name: string) {
    setSelectedEntity(name);
    setEntityRels(null);
    setShowSuggest(false);
    try {
      const token = localStorage.getItem("token") ?? "";
      const res = await fetch(`/api/admin/cypher/execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ query: `MATCH (e {name: $n})\nOPTIONAL MATCH (e)<-[]-(s:Section)<-[]-(d:Document)\nRETURN count(DISTINCT d) AS doc_count, count(DISTINCT s) AS section_count`, params: { n: name } }),
      });
      if (res.ok) {
        const d = await res.json();
        const row = d.rows?.[0] ?? {};
        setEntityRels({ doc_count: row.doc_count ?? 0, section_count: row.section_count ?? 0, tools: [], materials: [], related_entities: [] });
      }
    } catch { /* ignore */ }
  }

  function renderHighlight(r: SearchResult) {
    return r.highlight?.content?.[0] ?? r.snippet;
  }

  const hasAnySuggest = suggest && (suggest.documents.length + suggest.sections.length + suggest.entities.length + suggest.suggested_questions.length > 0);

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <h1 className="text-2xl font-semibold text-white mb-6">全局搜索</h1>

      {/* Search bar + dropdown */}
      <div className="relative mb-6">
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
            <input ref={inputRef} value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={e => e.key === "Enter" && handleSearch()}
              onFocus={() => hasAnySuggest && setShowSuggest(true)}
              onBlur={() => setTimeout(() => setShowSuggest(false), 150)}
              placeholder="搜索章节内容，支持中文关键词..."
              className="w-full pl-9 pr-4 py-2.5 bg-gray-900 border border-gray-700 rounded-xl text-gray-200 text-sm outline-none focus:border-indigo-500 placeholder-gray-600"
            />
          </div>
          <button onClick={() => handleSearch()} disabled={!query.trim() || loading}
            className="px-5 py-2.5 bg-indigo-600 text-white text-sm rounded-xl hover:bg-indigo-500 disabled:opacity-40">
            {loading ? "搜索中..." : "搜索"}
          </button>
        </div>

        {/* Suggestion dropdown */}
        {showSuggest && hasAnySuggest && (
          <div className="absolute top-full left-0 right-0 mt-1 bg-gray-900 border border-gray-700 rounded-xl shadow-2xl z-30 overflow-hidden">
            {suggest!.documents.length > 0 && (
              <SuggestGroup icon={<FileText size={12} className="text-indigo-400" />} label="文档">
                {suggest!.documents.map(d => (
                  <SuggestItem key={d.doc_id} onMouseDown={() => { handleSearch(d.doc_id); setQuery(d.doc_id); }}>
                    <span className="font-mono text-indigo-400 text-xs">{d.doc_id}</span>
                    <span className="text-gray-400 text-xs ml-2 truncate">{d.title}</span>
                  </SuggestItem>
                ))}
              </SuggestGroup>
            )}
            {suggest!.sections.length > 0 && (
              <SuggestGroup icon={<BookOpen size={12} className="text-amber-400" />} label="章节">
                {suggest!.sections.map(s => (
                  <SuggestItem key={s.chunk_id} onMouseDown={() => { handleSearch(s.title); setQuery(s.title); }}>
                    <span className="font-mono text-amber-400 text-xs">{s.doc_id}</span>
                    <span className="text-gray-300 text-xs ml-2 truncate">{s.title}</span>
                  </SuggestItem>
                ))}
              </SuggestGroup>
            )}
            {suggest!.entities.length > 0 && (
              <SuggestGroup icon={<Tag size={12} className="text-emerald-400" />} label="相关实体">
                {suggest!.entities.map(e => (
                  <SuggestItem key={e.name} onMouseDown={() => handleEntityClick(e.name)}>
                    <span className="text-emerald-300 text-xs">{e.name}</span>
                    <span className="text-gray-500 text-xs ml-2">出现 {e.mention_count} 次</span>
                  </SuggestItem>
                ))}
              </SuggestGroup>
            )}
            {suggest!.suggested_questions.length > 0 && (
              <SuggestGroup icon={<MessageSquare size={12} className="text-violet-400" />} label="直接提问">
                {suggest!.suggested_questions.map(q => (
                  <SuggestItem key={q} onMouseDown={() => window.location.href = `/query?q=${encodeURIComponent(q)}`}>
                    <span className="text-violet-300 text-xs">{q}</span>
                  </SuggestItem>
                ))}
              </SuggestGroup>
            )}
          </div>
        )}
      </div>

      {/* Entity relationship panel */}
      {selectedEntity && (
        <div className="mb-6 p-4 bg-gray-900 border border-gray-700 rounded-xl">
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm font-medium text-white">{selectedEntity} 的关系</span>
            <div className="flex gap-2">
              <Link href={`/graph?nf=Entity`} className="flex items-center gap-1 px-3 py-1 bg-gray-800 text-xs text-gray-300 rounded-lg hover:text-white border border-gray-700">
                <Network size={11} /> 查看图谱
              </Link>
              <button onClick={() => { setQuery(selectedEntity); handleSearch(selectedEntity); setSelectedEntity(null); }}
                className="px-3 py-1 bg-indigo-600 text-white text-xs rounded-lg hover:bg-indigo-500">搜索</button>
              <button onClick={() => setSelectedEntity(null)} className="text-gray-600 hover:text-gray-400 text-xs">✕</button>
            </div>
          </div>
          {entityRels ? (
            <div className="grid grid-cols-2 gap-3 text-xs text-gray-400">
              <div>📄 出现在 <span className="text-white">{entityRels.doc_count}</span> 份文档</div>
              <div>📑 关联 <span className="text-white">{entityRels.section_count}</span> 个章节</div>
            </div>
          ) : (
            <div className="text-xs text-gray-600">加载关系中…</div>
          )}
        </div>
      )}

      {total > 0 && <div className="text-xs text-gray-500 mb-4">找到 {total} 个相关章节</div>}

      <div className="space-y-3">
        {results.map(result => (
          <Link key={result.chunk_id} href={`/library/${result.doc_id}`}
            className="block p-4 bg-gray-900 rounded-xl border border-gray-800 hover:border-indigo-500 transition-colors">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <span className="text-xs font-mono text-indigo-400">{result.doc_id}</span>
                {result.number && <span className="text-xs text-gray-500">§{result.number}</span>}
                <span className="text-sm text-gray-200 font-medium">{result.title}</span>
              </div>
              <span className="text-xs text-gray-600">{result.score.toFixed(2)}</span>
            </div>
            <div className="text-xs text-gray-400 leading-relaxed line-clamp-3"
              dangerouslySetInnerHTML={{ __html: renderHighlight(result).replace(/<mark>/g, '<mark class="bg-indigo-500/30 text-indigo-300 rounded px-0.5">') }} />
          </Link>
        ))}
      </div>
    </div>
  );
}

function SuggestGroup({ icon, label, children }: { icon: React.ReactNode; label: string; children: React.ReactNode }) {
  return (
    <div className="border-b border-gray-800 last:border-0">
      <div className="flex items-center gap-1.5 px-3 pt-2 pb-1 text-[10px] font-medium text-gray-500 uppercase tracking-wide">
        {icon}{label}
      </div>
      {children}
    </div>
  );
}

function SuggestItem({ children, onMouseDown }: { children: React.ReactNode; onMouseDown: () => void }) {
  return (
    <button type="button" onMouseDown={onMouseDown}
      className="w-full flex items-center gap-2 px-3 py-2 hover:bg-gray-800 transition-colors text-left">
      {children}
    </button>
  );
}
