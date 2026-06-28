"use client";

import { BookOpen, ChevronLeft, ChevronRight, ExternalLink, Search } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { fetchApi } from "@/lib/api";

interface WikiDoc {
  doc_id: string;
  title: string;
  spec_type: string;
  section_count: number;
}

const PAGE_SIZE = 18;

export default function WikiIndexPage() {
  const [docs, setDocs] = useState<WikiDoc[]>([]);
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);

  useEffect(() => {
    fetchApi<WikiDoc[]>("/api/wiki/index")
      .then(setDocs)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  // Reset page when search changes
  useEffect(() => { setPage(1); }, [q]);

  const filtered = docs.filter(
    (d) => !q || d.doc_id.toLowerCase().includes(q.toLowerCase()) ||
           (d.title || "").toLowerCase().includes(q.toLowerCase())
  );

  const byType = filtered.reduce<Record<string, WikiDoc[]>>((acc, d) => {
    const key = d.spec_type || "通用";
    (acc[key] ||= []).push(d);
    return acc;
  }, {});

  // Flatten into pages (paginate across all types together)
  const allDocs = filtered;
  const totalPages = Math.max(1, Math.ceil(allDocs.length / PAGE_SIZE));
  const pageDocs = new Set(allDocs.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE).map(d => d.doc_id));

  // Filter byType to only show current-page docs
  const byTypeOnPage: Record<string, WikiDoc[]> = {};
  for (const [type, items] of Object.entries(byType)) {
    const pageItems = items.filter(d => pageDocs.has(d.doc_id));
    if (pageItems.length > 0) byTypeOnPage[type] = pageItems;
  }

  return (
    <div className="flex-1 overflow-auto bg-gray-950 p-6">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="mb-6" style={{ animation: "slide-up-fade 0.55s ease both" }}>
          <h1 className="text-xl font-bold text-gray-100 flex items-center gap-2">
            <BookOpen size={20} className="text-indigo-400" />
            规范百科
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            浏览所有已入库的工艺规范，点击查看详情卡片
          </p>
        </div>

        {/* Search */}
        <div className="relative mb-6">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-600 pointer-events-none" />
          <input value={q} onChange={(e) => setQ(e.target.value)}
            placeholder="搜索规范编号或标题…"
            className="w-full pl-9 pr-4 py-2.5 bg-gray-900 border border-gray-800 rounded-xl
                       text-sm text-gray-300 outline-none focus:border-indigo-700 placeholder-gray-600" />
        </div>

        {loading ? (
          <p className="text-xs text-gray-600 text-center py-12">加载中…</p>
        ) : docs.length === 0 ? (
          <p className="text-xs text-gray-600 text-center py-12">
            暂无规范数据。请先通过文档库上传并解析规范文件。
          </p>
        ) : (
          <>
            {Object.entries(byTypeOnPage).map(([type, items]) => (
              <div key={type} className="mb-8">
                <h2 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-3"
                  style={{ animation: "slide-in-left 0.4s ease both" }}>
                  {type} <span className="text-gray-700">({byType[type].length})</span>
                </h2>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 stagger-children">
                  {items.map((doc) => (
                    <Link key={doc.doc_id} href={`/wiki/${doc.doc_id}`}
                      className="group block p-4 bg-gray-900 border border-gray-800
                                 rounded-xl hover:border-indigo-700 transition-colors tech-card">
                      <div className="flex items-start justify-between gap-2">
                        <span className="text-xs font-semibold text-indigo-400 font-mono">
                          {doc.doc_id}
                        </span>
                        <ExternalLink size={11} className="text-gray-700 group-hover:text-gray-500 shrink-0 mt-0.5" />
                      </div>
                      <p className="text-sm text-gray-300 mt-1 line-clamp-2">
                        {doc.title || doc.doc_id}
                      </p>
                      <p className="text-[10px] text-gray-600 mt-2">
                        {doc.section_count} 个章节
                      </p>
                    </Link>
                  ))}
                </div>
              </div>
            ))}

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between mt-4 pt-4 border-t border-gray-800">
                <span className="text-xs text-gray-500">
                  第 {page} / {totalPages} 页 · 共 {filtered.length} 份规范
                </span>
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => setPage(p => Math.max(1, p - 1))}
                    disabled={page === 1}
                    className="p-1.5 rounded-lg text-gray-500 hover:text-white hover:bg-gray-800 disabled:opacity-30 transition-colors"
                  >
                    <ChevronLeft size={15} />
                  </button>
                  {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
                    const n = totalPages <= 7 ? i + 1
                      : page <= 4 ? i + 1
                      : page >= totalPages - 3 ? totalPages - 6 + i
                      : page - 3 + i;
                    return (
                      <button key={n} onClick={() => setPage(n)}
                        className={`w-7 h-7 text-xs rounded-lg transition-colors ${
                          n === page
                            ? "bg-indigo-600 text-white"
                            : "text-gray-500 hover:text-white hover:bg-gray-800"
                        }`}>
                        {n}
                      </button>
                    );
                  })}
                  <button
                    onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                    disabled={page === totalPages}
                    className="p-1.5 rounded-lg text-gray-500 hover:text-white hover:bg-gray-800 disabled:opacity-30 transition-colors"
                  >
                    <ChevronRight size={15} />
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
