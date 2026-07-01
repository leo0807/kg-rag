"use client";

import { BookOpen, ChevronLeft, ChevronRight, Layers, FileText, Search, ExternalLink } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { fetchApi } from "@/lib/api";

interface WikiDoc { doc_id: string; title: string; spec_type: string; section_count: number }

const PAGE_SIZE = 18;

const TYPE_COLOR: Record<string, { bg: string; text: string; border: string }> = {
  "工艺规范": { bg: "bg-blue-500/10",   text: "text-blue-400",   border: "border-blue-500/20" },
  "材料规范": { bg: "bg-emerald-500/10", text: "text-emerald-400", border: "border-emerald-500/20" },
  "质量规范": { bg: "bg-amber-500/10",  text: "text-amber-400",  border: "border-amber-500/20" },
  "设计规范": { bg: "bg-violet-500/10", text: "text-violet-400", border: "border-violet-500/20" },
  "通用":     { bg: "bg-gray-700/30",   text: "text-gray-400",   border: "border-gray-700/40" },
};

function typeColor(t: string) {
  return TYPE_COLOR[t] ?? TYPE_COLOR["通用"];
}

export default function WikiIndexPage() {
  const [docs, setDocs] = useState<WikiDoc[]>([]);
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);

  useEffect(() => {
    fetchApi<WikiDoc[]>("/api/wiki/index").then(setDocs).catch(() => {}).finally(() => setLoading(false));
  }, []);

  useEffect(() => { setPage(1); }, [q]);

  const filtered = docs.filter(d =>
    !q || d.doc_id.toLowerCase().includes(q.toLowerCase()) ||
    (d.title || "").toLowerCase().includes(q.toLowerCase())
  );

  const byType = filtered.reduce<Record<string, WikiDoc[]>>((acc, d) => {
    const key = d.spec_type || "通用";
    (acc[key] ||= []).push(d);
    return acc;
  }, {});

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const pageDocIds = new Set(filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE).map(d => d.doc_id));

  const byTypeOnPage: Record<string, WikiDoc[]> = {};
  for (const [type, items] of Object.entries(byType)) {
    const pageItems = items.filter(d => pageDocIds.has(d.doc_id));
    if (pageItems.length > 0) byTypeOnPage[type] = pageItems;
  }

  return (
    <div className="flex-1 overflow-auto bg-gray-950 p-6">
      <div className="max-w-5xl mx-auto space-y-6">
        {/* Hero header */}
        <div className="rounded-2xl border border-gray-800 bg-[radial-gradient(ellipse_at_top_left,rgba(99,102,241,0.1),transparent_50%),#0f1117] p-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h1 className="text-xl font-semibold text-white flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center">
                  <BookOpen size={15} className="text-indigo-400" />
                </div>
                规范百科
              </h1>
              <p className="text-sm text-gray-500 mt-2 ml-[42px]">浏览所有已入库的工艺规范 · 点击查看详情卡片</p>
            </div>
            {!loading && docs.length > 0 && (
              <div className="flex items-center gap-4 shrink-0">
                <div className="text-center">
                  <div className="text-xl font-bold text-white">{docs.length}</div>
                  <div className="text-[10px] text-gray-600 mt-0.5">规范文档</div>
                </div>
                <div className="w-px h-8 bg-gray-800" />
                <div className="text-center">
                  <div className="text-xl font-bold text-white">{Object.keys(byType).length}</div>
                  <div className="text-[10px] text-gray-600 mt-0.5">规范类型</div>
                </div>
                <div className="w-px h-8 bg-gray-800" />
                <div className="text-center">
                  <div className="text-xl font-bold text-white">{docs.reduce((s, d) => s + d.section_count, 0).toLocaleString()}</div>
                  <div className="text-[10px] text-gray-600 mt-0.5">章节总数</div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Search */}
        <div className="relative">
          <Search size={14} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-600 pointer-events-none" />
          <input value={q} onChange={e => setQ(e.target.value)}
            placeholder="搜索规范编号或标题…"
            className="w-full pl-10 pr-4 py-2.5 bg-gray-900 border border-gray-800 rounded-xl text-sm text-gray-300 outline-none focus:border-indigo-600/60 placeholder-gray-600 transition-colors" />
          {q && (
            <span className="absolute right-3.5 top-1/2 -translate-y-1/2 text-xs text-gray-600">
              {filtered.length} 条
            </span>
          )}
        </div>

        {loading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {Array.from({ length: 9 }).map((_, i) => (
              <div key={i} className="h-28 rounded-xl border border-gray-800 bg-gray-900 animate-pulse" />
            ))}
          </div>
        ) : docs.length === 0 ? (
          <div className="text-center py-16">
            <FileText size={36} className="text-gray-800 mx-auto mb-3" />
            <p className="text-sm text-gray-600">暂无规范数据，请先通过文档库上传并解析规范文件</p>
          </div>
        ) : (
          <>
            {Object.entries(byTypeOnPage).map(([type, items]) => {
              const c = typeColor(type);
              return (
                <div key={type}>
                  <div className="flex items-center gap-2 mb-3">
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium border ${c.bg} ${c.text} ${c.border}`}>
                      {type}
                    </span>
                    <span className="text-xs text-gray-700">{byType[type].length} 份</span>
                    <div className="flex-1 h-px bg-gray-800/60" />
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 stagger-scale">
                    {items.map(doc => (
                      <Link key={doc.doc_id} href={`/wiki/${doc.doc_id}`}
                        className="group relative flex flex-col p-4 bg-gray-900 border border-gray-800 rounded-xl hover:border-gray-700 hover:bg-gray-900/80 transition-all hover-lift">
                        {/* Top row */}
                        <div className="flex items-start justify-between gap-2 mb-2">
                          <span className="text-xs font-mono font-semibold text-indigo-400 leading-tight">{doc.doc_id}</span>
                          <ExternalLink size={11} className="text-gray-700 group-hover:text-gray-500 shrink-0 mt-0.5 transition-colors" />
                        </div>
                        {/* Title */}
                        <p className="text-sm text-gray-300 line-clamp-2 leading-snug flex-1 mb-3">
                          {doc.title || doc.doc_id}
                        </p>
                        {/* Footer */}
                        <div className="flex items-center gap-2 pt-2 border-t border-gray-800/60">
                          <Layers size={11} className="text-gray-700" />
                          <span className="text-[10px] text-gray-600">{doc.section_count} 个章节</span>
                        </div>
                        {/* Hover glow */}
                        <div className="absolute inset-0 rounded-xl pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity"
                          style={{ boxShadow: "inset 0 0 20px rgba(99,102,241,0.03)" }} />
                      </Link>
                    ))}
                  </div>
                </div>
              );
            })}

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between pt-4 border-t border-gray-800">
                <span className="text-xs text-gray-600">第 {page} / {totalPages} 页 · 共 {filtered.length} 份规范</span>
                <div className="flex items-center gap-1">
                  <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
                    className="p-1.5 rounded-lg text-gray-500 hover:text-white hover:bg-gray-800 disabled:opacity-30 transition-colors">
                    <ChevronLeft size={14} />
                  </button>
                  {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
                    const n = totalPages <= 7 ? i + 1
                      : page <= 4 ? i + 1
                      : page >= totalPages - 3 ? totalPages - 6 + i
                      : page - 3 + i;
                    return (
                      <button key={n} onClick={() => setPage(n)}
                        className={`w-7 h-7 text-xs rounded-lg transition-colors ${n === page ? "bg-indigo-600 text-white" : "text-gray-500 hover:text-white hover:bg-gray-800"}`}>
                        {n}
                      </button>
                    );
                  })}
                  <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages}
                    className="p-1.5 rounded-lg text-gray-500 hover:text-white hover:bg-gray-800 disabled:opacity-30 transition-colors">
                    <ChevronRight size={14} />
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
