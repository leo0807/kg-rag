"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { fetchApi } from "@/lib/api";
import SkeletonTable from "@/components/ui/SkeletonTable";
import { LibraryIngestTab } from "./LibraryIngestTab";
import { LibraryReprocessTab } from "./LibraryReprocessTab";
import BackfillProgressBar from "@/components/BackfillProgressBar";
import { ExportMenu } from "./ExportMenu";

interface Document {
  doc_id: string;
  title: string | null;
  version: string | null;
  issue_date: string | null;
  section_count: number;
  image_count: number;
  analyzed_image_count: number;
  analysis_status: "none" | "pending" | "partial" | "analyzed";
}
interface PagedResponse {
  data: Document[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}
function ImageAnalysisBadge({
  status,
  imageCount,
  analyzedCount,
}: {
  status: Document["analysis_status"];
  imageCount: number;
  analyzedCount: number;
}) {
  if (status === "none" || imageCount === 0) {
    return <span className="text-gray-600 text-xs">—</span>;
  }
  if (status === "analyzed") {
    return (
      <span
        className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs
                             bg-green-900/40 text-green-400 border border-green-700/40"
      >
        <span className="w-1.5 h-1.5 rounded-full bg-green-400" />
        已分析 {imageCount} 张
      </span>
    );
  }
  if (status === "partial") {
    return (
      <span
        className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs
                             bg-yellow-900/40 text-yellow-400 border border-yellow-700/40"
      >
        <span className="w-1.5 h-1.5 rounded-full bg-yellow-400" />
        分析中 {analyzedCount}/{imageCount}
      </span>
    );
  }
  // pending
  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs
                         bg-gray-800 text-gray-500 border border-gray-700/40"
    >
      <span className="w-1.5 h-1.5 rounded-full bg-gray-600" />
      待分析 {imageCount} 张
    </span>
  );
}

function getIsAdmin(): boolean {
  try {
    return JSON.parse(localStorage.getItem("user") || "{}").is_admin === true;
  } catch {
    return false;
  }
}

export default function LibraryPage() {
  const [docs, setDocs] = useState<Document[]>([]);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);
  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);
  const [activeTab, setActiveTab] = useState<"list" | "ingest" | "reprocess">(
    "list",
  );

  useEffect(() => {
    setIsAdmin(getIsAdmin());
    // Restore tab from URL hash on mount
    const hash = window.location.hash.slice(1);
    if (hash === "ingest" || hash === "reprocess") setActiveTab(hash);
  }, []);

  function switchTab(tab: "list" | "ingest" | "reprocess") {
    setActiveTab(tab);
    history.replaceState(
      null,
      "",
      tab === "list"
        ? window.location.pathname
        : `${window.location.pathname}#${tab}`,
    );
  }

  useEffect(() => {
    if (activeTab !== "list") return;
    setLoading(true);
    setFetchError(false);
    const params = new URLSearchParams({
      page: String(page),
      per_page: "20",
      q: search,
    });
    fetchApi<PagedResponse>(`/api/documents?${params}`)
      .then((data: PagedResponse) => {
        setDocs(data.data);
        setTotal(data.total);
        setPages(data.pages);
      })
      .catch(() => setFetchError(true))
      .finally(() => setLoading(false));
  }, [page, search, activeTab]);

  function handleSearch(e: { preventDefault(): void }) {
    e.preventDefault();
    setPage(1);
    setSearch(q);
  }

  return (
    <div className="p-8 max-w-6xl mx-auto">
      {/* 标题行 + 选项卡 */}
      <div className="flex items-center justify-between mb-2">
        <h1 className="text-2xl font-semibold text-white">
          文档库
          {activeTab === "list" && (
            <span className="ml-3 text-sm text-gray-400 font-normal">
              {total} 个文档
            </span>
          )}
        </h1>
        {activeTab === "list" && (
          <form onSubmit={handleSearch} className="flex gap-2 items-center">
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="搜索规范编号或标题..."
              className="px-3 py-1.5 bg-gray-900 border border-gray-700 rounded-lg text-sm
                                       text-gray-200 outline-none focus:border-[#1B6BB5] placeholder-gray-600 w-56"
            />
            <button
              type="submit"
              className="px-3 py-1.5 bg-[#1B6BB5] text-white text-sm rounded-lg hover:bg-[#1558A0]"
            >
              搜索
            </button>
            {search && (
              <button
                type="button"
                onClick={() => {
                  setQ("");
                  setSearch("");
                  setPage(1);
                }}
                className="px-3 py-1.5 bg-gray-800 text-gray-400 text-sm rounded-lg hover:text-white"
              >
                清除
              </button>
            )}
            <ExportMenu />
          </form>
        )}
      </div>

      {/* 选项卡 */}
      <div className="flex items-center gap-1 border-b border-gray-800 mb-5">
        <button
          onClick={() => switchTab("list")}
          className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${activeTab === "list" ? "border-[#1B6BB5] text-[#1B6BB5] dark:text-white" : "border-transparent text-gray-500 hover:text-gray-300"}`}
        >
          文档列表
        </button>
        {isAdmin && (
          <button
            onClick={() => switchTab("ingest")}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${activeTab === "ingest" ? "border-[#1B6BB5] text-[#1B6BB5] dark:text-white" : "border-transparent text-gray-500 hover:text-gray-300"}`}
          >
            导入文件
          </button>
        )}
        <button
          onClick={() => switchTab("reprocess")}
          className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${activeTab === "reprocess" ? "border-[#1B6BB5] text-[#1B6BB5] dark:text-white" : "border-transparent text-gray-500 hover:text-gray-300"}`}
        >
          重新处理
        </button>
      </div>

      {activeTab === "ingest" && isAdmin && (
        <LibraryIngestTab
          onDone={() => {
            switchTab("list");
            setPage(1);
            setSearch("");
          }}
        />
      )}
      {activeTab === "reprocess" && <LibraryReprocessTab isAdmin={isAdmin} />}

      {activeTab === "list" && (
        <>
          <BackfillProgressBar />
          {fetchError && (
            <div className="px-4 py-3 bg-red-500/10 border border-red-500/30 rounded-lg text-sm text-red-400 mb-4">
              加载失败，请刷新页面重试
            </div>
          )}
          {loading && docs.length === 0 ? (
            <SkeletonTable rows={10} />
          ) : (
            !fetchError && (
              <div className="relative">
                {loading && (
                  <div className="absolute inset-0 bg-gray-950/50 z-10 pointer-events-none rounded" />
                )}
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-800 text-gray-400 text-left">
                      <th className="pb-3 pr-6">规范编号</th>
                      <th className="pb-3 pr-6">标题</th>
                      <th className="pb-3 pr-6">版本</th>
                      <th className="pb-3 pr-6">发布日期</th>
                      <th className="pb-3 pr-4">章节数</th>
                      <th className="pb-3">图片分析</th>
                    </tr>
                  </thead>
                  <tbody>
                    {docs.length === 0 && (
                      <tr>
                        <td
                          colSpan={6}
                          className="py-12 text-center text-sm text-gray-500"
                        >
                          {search
                            ? `未找到与"${search}"相关的文档`
                            : "暂无文档"}
                        </td>
                      </tr>
                    )}
                    {docs.map((doc) => (
                      <tr
                        key={doc.doc_id}
                        className="border-b border-gray-800/50"
                      >
                        <td className="py-3 pr-6 font-mono text-[#1B6BB5] dark:text-[#5BA3E0]">
                          <Link
                            href={`/library/${doc.doc_id}`}
                            className="hover:underline"
                          >
                            {doc.doc_id}
                          </Link>
                        </td>
                        <td className="py-3 pr-6 text-gray-300">
                          {doc.title ?? "—"}
                        </td>
                        <td className="py-3 pr-6 text-gray-400">
                          {doc.version ?? "—"}
                        </td>
                        <td className="py-3 pr-6 text-gray-400">
                          {doc.issue_date ?? "—"}
                        </td>
                        <td className="py-3 pr-4 text-gray-400">
                          {doc.section_count}
                        </td>
                        <td className="py-3">
                          <ImageAnalysisBadge
                            status={doc.analysis_status}
                            imageCount={doc.image_count ?? 0}
                            analyzedCount={doc.analyzed_image_count ?? 0}
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {pages > 1 && (
                  <div className="flex items-center gap-2 mt-6">
                    <button
                      onClick={() => setPage((p) => Math.max(1, p - 1))}
                      disabled={page === 1}
                      className="px-3 py-1.5 bg-gray-900 border border-gray-700 rounded text-sm text-gray-300 hover:border-gray-500 disabled:opacity-40"
                    >
                      上一页
                    </button>
                    <span className="text-sm text-gray-500">
                      第 {page} / {pages} 页
                    </span>
                    <button
                      onClick={() => setPage((p) => Math.min(pages, p + 1))}
                      disabled={page === pages}
                      className="px-3 py-1.5 bg-gray-900 border border-gray-700 rounded text-sm text-gray-300 hover:border-gray-500 disabled:opacity-40"
                    >
                      下一页
                    </button>
                  </div>
                )}
              </div>
            )
          )}
        </>
      )}
    </div>
  );
}
