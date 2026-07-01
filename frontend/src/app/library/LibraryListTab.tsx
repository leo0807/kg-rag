"use client";

import Link from "next/link";
import { FileText, Layers, ImageIcon, ChevronLeft, ChevronRight, Search, X } from "lucide-react";
import { useState, useEffect } from "react";
import { fetchApi } from "@/lib/api";
import SkeletonTable from "@/components/ui/SkeletonTable";
import BackfillProgressBar from "@/components/BackfillProgressBar";
import { ExportMenu } from "./ExportMenu";

interface Document {
  doc_id: string; title: string | null; version: string | null;
  issue_date: string | null; section_count: number;
  image_count: number; analyzed_image_count: number;
  analysis_status: "none" | "pending" | "partial" | "analyzed";
}
interface PagedResponse { data: Document[]; total: number; page: number; per_page: number; pages: number }

function StatusBadge({ status, imageCount, analyzedCount }: {
  status: Document["analysis_status"]; imageCount: number; analyzedCount: number;
}) {
  if (status === "none" || imageCount === 0) return <span className="text-gray-700 text-xs">—</span>;
  const configs = {
    analyzed: { dot: "bg-emerald-400", text: "text-emerald-400", bg: "bg-emerald-900/30 border-emerald-700/30", label: `已分析 ${imageCount}` },
    partial:  { dot: "bg-amber-400",   text: "text-amber-400",   bg: "bg-amber-900/30 border-amber-700/30",   label: `${analyzedCount}/${imageCount}` },
    pending:  { dot: "bg-gray-500",    text: "text-gray-500",    bg: "bg-gray-800/50 border-gray-700/30",     label: `待分析 ${imageCount}` },
  } as const;
  const c = configs[status as keyof typeof configs] ?? configs.pending;
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs border ${c.bg} ${c.text}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${c.dot}`} />
      {c.label}
    </span>
  );
}

function SectionBar({ count }: { count: number }) {
  const maxSections = 200;
  const w = Math.min((count / maxSections) * 100, 100);
  return (
    <div className="flex items-center gap-2">
      <div className="w-20 h-1.5 bg-gray-800 rounded-full overflow-hidden">
        <div className="h-full rounded-full bg-indigo-500/60 transition-all" style={{ width: `${w}%` }} />
      </div>
      <span className="text-gray-400 text-xs tabular-nums">{count}</span>
    </div>
  );
}

export function LibraryListTab() {
  const [docs, setDocs] = useState<Document[]>([]);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);
  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState(false);

  useEffect(() => {
    setLoading(true); setFetchError(false);
    const params = new URLSearchParams({ page: String(page), per_page: "20", q: search });
    fetchApi<PagedResponse>(`/api/documents?${params}`)
      .then(d => { setDocs(d.data); setTotal(d.total); setPages(d.pages); })
      .catch(() => setFetchError(true))
      .finally(() => setLoading(false));
  }, [page, search]);

  function handleSearch(e: { preventDefault(): void }) {
    e.preventDefault(); setPage(1); setSearch(q);
  }

  return (
    <div className="space-y-4">
      <BackfillProgressBar />

      {/* Search bar + export */}
      <div className="flex items-center gap-3">
        <form onSubmit={handleSearch} className="flex items-center flex-1 max-w-sm gap-2">
          <div className="relative flex-1">
            <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none" />
            <input value={q} onChange={e => setQ(e.target.value)}
              placeholder="规范编号或标题…"
              className="w-full pl-8 pr-3 py-1.5 bg-gray-900 border border-gray-700 rounded-lg text-sm text-gray-200 outline-none focus:border-blue-500/60 placeholder-gray-600" />
          </div>
          <button type="submit" className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded-lg transition-colors">搜索</button>
          {search && (
            <button type="button" onClick={() => { setQ(""); setSearch(""); setPage(1); }}
              className="p-1.5 text-gray-500 hover:text-gray-300 transition-colors">
              <X size={14} />
            </button>
          )}
        </form>
        <div className="ml-auto"><ExportMenu /></div>
      </div>

      {fetchError && (
        <div className="px-4 py-3 bg-red-500/10 border border-red-500/30 rounded-lg text-sm text-red-400">加载失败，请刷新重试</div>
      )}

      {loading && docs.length === 0 ? <SkeletonTable rows={10} /> : !fetchError && (
        <div className="relative bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
          {loading && <div className="absolute inset-0 bg-gray-950/50 z-10 pointer-events-none" />}
          <table className="w-full text-sm">
            <thead className="border-b border-gray-800">
              <tr>
                {["规范编号", "标题", "版本", "发布日期", "章节数", "图片分析"].map(h => (
                  <th key={h} className="text-left px-4 py-3 text-xs text-gray-500 font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800/60">
              {docs.length === 0 ? (
                <tr><td colSpan={6} className="py-16 text-center text-sm text-gray-600">
                  {search ? `未找到"${search}"相关文档` : "暂无文档"}
                </td></tr>
              ) : docs.map(doc => (
                <tr key={doc.doc_id} className="hover:bg-gray-800/30 transition-colors group">
                  <td className="px-4 py-3">
                    <Link href={`/library/${doc.doc_id}`}
                      className="font-mono text-blue-400 hover:text-blue-300 text-sm group-hover:underline">
                      {doc.doc_id}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-gray-300 text-sm max-w-xs truncate">{doc.title ?? "—"}</td>
                  <td className="px-4 py-3">
                    {doc.version ? (
                      <span className="px-2 py-0.5 rounded-full text-xs bg-gray-800 text-gray-400 border border-gray-700/60 font-mono">{doc.version}</span>
                    ) : <span className="text-gray-600 text-xs">—</span>}
                  </td>
                  <td className="px-4 py-3 text-gray-500 text-xs">{doc.issue_date ?? "—"}</td>
                  <td className="px-4 py-3"><SectionBar count={doc.section_count} /></td>
                  <td className="px-4 py-3">
                    <StatusBadge status={doc.analysis_status} imageCount={doc.image_count ?? 0} analyzedCount={doc.analyzed_image_count ?? 0} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {pages > 1 && (
            <div className="flex items-center justify-between px-4 py-3 border-t border-gray-800">
              <span className="text-xs text-gray-600">共 {total} 个文档</span>
              <div className="flex items-center gap-2">
                <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
                  className="flex items-center gap-1 px-2.5 py-1 text-xs rounded border border-gray-700 text-gray-400 hover:text-gray-200 hover:border-gray-500 disabled:opacity-30 transition-colors">
                  <ChevronLeft size={12} /> 上一页
                </button>
                <span className="text-xs text-gray-500 px-1">第 {page} / {pages} 页</span>
                <button onClick={() => setPage(p => Math.min(pages, p + 1))} disabled={page === pages}
                  className="flex items-center gap-1 px-2.5 py-1 text-xs rounded border border-gray-700 text-gray-400 hover:text-gray-200 hover:border-gray-500 disabled:opacity-30 transition-colors">
                  下一页 <ChevronRight size={12} />
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export { FileText, Layers, ImageIcon };
