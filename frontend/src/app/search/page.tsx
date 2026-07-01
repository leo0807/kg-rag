"use client";

import Link from "next/link";
import { useRef, useState } from "react";
import { Network, Search } from "lucide-react";
import { fetchApi } from "@/lib/api";
import { SuggestDropdown } from "./SuggestDropdown";

interface SearchResult {
  chunk_id: string; doc_id: string; number: string; title: string;
  snippet: string; score: number; highlight?: Record<string, string[]>;
}
interface SuggestResult {
  documents:           { doc_id: string; title: string; relevance: number }[];
  sections:            { chunk_id: string; title: string; doc_id: string; relevance: number }[];
  entities:            { name: string; type: string; mention_count: number }[];
  suggested_questions: string[];
}
interface EntityRels { doc_count: number; section_count: number }

const HOT_KEYWORDS = ["铆接工艺", "复合材料", "密封要求", "热处理", "表面处理"];

export default function SearchPage() {
  const [query,       setQuery]       = useState("");
  const [results,     setResults]     = useState<SearchResult[]>([]);
  const [total,       setTotal]       = useState(0);
  const [loading,     setLoading]     = useState(false);
  const [suggest,     setSuggest]     = useState<SuggestResult | null>(null);
  const [showSug,     setShowSug]     = useState(false);
  const [entity,      setEntity]      = useState<string | null>(null);
  const [rels,        setRels]        = useState<EntityRels | null>(null);
  const [hasSearched, setHasSearched] = useState(false);
  const debRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  function onQueryChange(val: string) {
    setQuery(val);
    if (!val.trim() || val.length < 2) { setSuggest(null); setShowSug(false); return; }
    if (debRef.current) clearTimeout(debRef.current);
    debRef.current = setTimeout(async () => {
      try {
        const d = await fetchApi<SuggestResult>(`/api/search/suggest?q=${encodeURIComponent(val)}&limit=5`);
        setSuggest(d); setShowSug(true);
      } catch { /* ignore */ }
    }, 300);
  }

  async function handleSearch(q = query) {
    if (!q.trim()) return;
    setQuery(q); setShowSug(false); setLoading(true); setHasSearched(true);
    try {
      const d = await fetchApi<{ results: SearchResult[]; total: number }>(
        `/api/search?q=${encodeURIComponent(q)}&top_k=20`
      );
      setResults(d.results); setTotal(d.total);
    } finally { setLoading(false); }
  }

  async function handleEntityClick(name: string) {
    setEntity(name); setRels(null); setShowSug(false);
    try {
      const d = await fetchApi<{ rows?: Record<string, number>[] }>(`/api/admin/cypher/execute`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: `MATCH (e {name: $n}) OPTIONAL MATCH (e)<-[]-(s:Section)<-[]-(d:Document) RETURN count(DISTINCT d) AS doc_count, count(DISTINCT s) AS section_count`,
          params: { n: name },
        }),
      });
      const row = d.rows?.[0] ?? {};
      setRels({ doc_count: row.doc_count ?? 0, section_count: row.section_count ?? 0 });
    } catch { /* ignore */ }
  }

  const hasSug   = suggest && (suggest.documents.length + suggest.sections.length + suggest.entities.length + suggest.suggested_questions.length > 0);
  const maxScore = results.length ? results[0].score : 1;

  return (
    <div className="min-h-screen bg-gray-950">
      {/* Hero */}
      <div className="bg-[radial-gradient(ellipse_at_top,rgba(99,102,241,0.15),transparent_60%)] border-b border-gray-800/60 px-4 py-8 sm:px-6 sm:py-10">
        <div className="max-w-2xl mx-auto">
          <div className="flex items-center gap-2 mb-3">
            <div className="w-8 h-8 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center">
              <Search size={15} className="text-indigo-400" />
            </div>
            <h1 className="text-lg font-semibold text-white">全局搜索</h1>
          </div>
          <p className="text-sm text-gray-500 mb-6">全文检索规范文档章节内容，支持关键词高亮</p>

          <div className="relative">
            <div className="flex gap-2">
              <div className="relative flex-1">
                <Search size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none" />
                <input
                  value={query}
                  onChange={e => onQueryChange(e.target.value)}
                  onKeyDown={e => e.key === "Enter" && handleSearch()}
                  onFocus={() => hasSug && setShowSug(true)}
                  onBlur={() => setTimeout(() => setShowSug(false), 150)}
                  placeholder="输入关键词搜索章节内容…"
                  className="w-full pl-10 pr-4 py-3 bg-gray-900 border border-gray-700/60 rounded-xl text-gray-200 text-sm outline-none focus:border-indigo-500/70 placeholder-gray-600 transition-colors"
                />
              </div>
              <button onClick={() => handleSearch()} disabled={!query.trim() || loading}
                className="px-5 py-3 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white text-sm rounded-xl font-medium transition-colors">
                {loading ? "搜索中…" : "搜索"}
              </button>
            </div>
            {showSug && hasSug && suggest && (
              <SuggestDropdown
                suggest={suggest}
                onSearchText={q => { handleSearch(q); }}
                onEntityClick={handleEntityClick}
              />
            )}
          </div>
        </div>
      </div>

      {/* Body */}
      <div className="max-w-2xl mx-auto px-4 py-4 sm:px-6 sm:py-6 space-y-4">
        {/* Entity panel */}
        {entity && (
          <div className="p-4 bg-gray-900 border border-gray-700/60 rounded-xl">
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm font-medium text-white">{entity}</span>
              <div className="flex gap-2">
                <Link href="/graph?nf=Entity"
                  className="flex items-center gap-1 px-2.5 py-1 bg-gray-800 text-xs text-gray-300 rounded-lg hover:text-white border border-gray-700 transition-colors">
                  <Network size={11} /> 图谱
                </Link>
                <button onClick={() => { handleSearch(entity); setEntity(null); }}
                  className="px-2.5 py-1 bg-indigo-600 text-white text-xs rounded-lg hover:bg-indigo-500 transition-colors">搜索</button>
                <button onClick={() => setEntity(null)} className="text-gray-600 hover:text-gray-400 text-xs px-1">✕</button>
              </div>
            </div>
            {rels ? (
              <div className="grid grid-cols-2 gap-3 text-xs text-gray-400">
                <div className="bg-gray-800/60 rounded-lg px-3 py-2">出现在 <span className="text-white font-medium">{rels.doc_count}</span> 份文档</div>
                <div className="bg-gray-800/60 rounded-lg px-3 py-2">关联 <span className="text-white font-medium">{rels.section_count}</span> 个章节</div>
              </div>
            ) : (
              <div className="text-xs text-gray-600 animate-pulse">加载关系中…</div>
            )}
          </div>
        )}

        {total > 0 && (
          <div className="flex items-center justify-between text-xs">
            <span className="text-gray-500">找到 <span className="text-white font-medium">{total}</span> 个相关章节</span>
            <span className="text-gray-600">按相关度排序</span>
          </div>
        )}

        {loading && (
          <div className="space-y-3">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-24 bg-gray-900 rounded-xl animate-pulse border border-gray-800" />
            ))}
          </div>
        )}

        {!loading && results.length > 0 && (
        <div className="stagger-children space-y-4">
        {results.map(r => (
          <Link key={r.chunk_id} href={`/library/${r.doc_id}`}
            className="block p-4 bg-gray-900 rounded-xl border border-gray-800 hover:border-indigo-500/50 transition-all group hover-lift">
            <div className="flex items-start justify-between gap-3 mb-2">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-[11px] font-mono text-indigo-400 bg-indigo-500/10 border border-indigo-500/20 px-2 py-0.5 rounded">
                  {r.doc_id}
                </span>
                {r.number && <span className="text-[11px] text-gray-500">§{r.number}</span>}
                <span className="text-sm text-gray-200 font-medium group-hover:text-white transition-colors">{r.title}</span>
              </div>
              <div className="flex items-center gap-1.5 shrink-0">
                <div className="w-16 h-1 bg-gray-800 rounded-full overflow-hidden">
                  <div className="h-full bg-indigo-500/70 rounded-full"
                    style={{ width: `${Math.min((r.score / maxScore) * 100, 100)}%` }} />
                </div>
                <span className="text-[10px] text-gray-600 tabular-nums">{r.score.toFixed(2)}</span>
              </div>
            </div>
            <div className="text-xs text-gray-400 leading-relaxed line-clamp-3"
              dangerouslySetInnerHTML={{
                __html: (r.highlight?.content?.[0] ?? r.snippet).replace(
                  /<mark>/g,
                  '<mark class="bg-indigo-500/25 text-indigo-300 rounded px-0.5 not-italic">'
                )
              }} />
          </Link>
        ))}
        </div>
        )}

        {!loading && hasSearched && results.length === 0 && (
          <div className="text-center py-16">
            <div className="w-12 h-12 rounded-2xl bg-gray-800 border border-gray-700 flex items-center justify-center mx-auto mb-3">
              <Search size={20} className="text-gray-600" />
            </div>
            <p className="text-sm text-gray-500 mb-1">未找到匹配的章节</p>
            <p className="text-xs text-gray-600">尝试更简短的关键词，或前往<Link href="/query" className="text-indigo-400 hover:underline">智能问答</Link></p>
          </div>
        )}

        {!hasSearched && !loading && (
          <div className="text-center py-12">
            <p className="text-sm text-gray-600 mb-4">输入关键词开始搜索，或选择热门方向</p>
            <div className="flex flex-wrap gap-2 justify-center">
              {HOT_KEYWORDS.map(kw => (
                <button key={kw} onClick={() => handleSearch(kw)}
                  className="px-3 py-1.5 bg-gray-900 border border-gray-800 text-gray-400 text-xs rounded-lg hover:border-indigo-500/50 hover:text-indigo-400 transition-colors">
                  {kw}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
