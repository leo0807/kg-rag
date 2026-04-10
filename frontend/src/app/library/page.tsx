"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import SkeletonTable from "@/components/ui/SkeletonTable";
import { LibraryReprocessTab } from "./LibraryReprocessTab";

interface Document {
    doc_id: string;
    title: string | null;
    version: string | null;
    issue_date: string | null;
    section_count: number;
}
interface PagedResponse {
    data: Document[]; total: number; page: number; per_page: number; pages: number;
}
function getIsAdmin(): boolean {
    try { return JSON.parse(localStorage.getItem("user") || "{}").is_admin === true; }
    catch { return false; }
}

export default function LibraryPage() {
    const [docs,       setDocs]       = useState<Document[]>([]);
    const [total,      setTotal]      = useState(0);
    const [pages,      setPages]      = useState(1);
    const [page,       setPage]       = useState(1);
    const [q,          setQ]          = useState("");
    const [search,     setSearch]     = useState("");
    const [loading,    setLoading]    = useState(true);
    const [fetchError, setFetchError] = useState(false);
    const [isAdmin,    setIsAdmin]    = useState(false);
    const [activeTab,  setActiveTab]  = useState<"list" | "reprocess">("list");

    useEffect(() => { setIsAdmin(getIsAdmin()); }, []);

    useEffect(() => {
        if (activeTab !== "list") return;
        setLoading(true);
        setFetchError(false);
        const params = new URLSearchParams({ page: String(page), per_page: "20", q: search });
        fetch(`/api/documents?${params}`)
            .then(r => { if (!r.ok) throw new Error(); return r.json(); })
            .then((data: PagedResponse) => {
                setDocs(data.data); setTotal(data.total); setPages(data.pages);
            })
            .catch(() => setFetchError(true))
            .finally(() => setLoading(false));
    }, [page, search, activeTab]);

    function handleSearch(e: { preventDefault(): void }) { e.preventDefault(); setPage(1); setSearch(q); }

    return (
        <div className="p-8 max-w-6xl mx-auto">
            {/* 标题行 + 选项卡 */}
            <div className="flex items-center justify-between mb-2">
                <h1 className="text-2xl font-semibold text-white">
                    文档库
                    {activeTab === "list" && (
                        <span className="ml-3 text-sm text-gray-400 font-normal">{total} 个文档</span>
                    )}
                </h1>
                {activeTab === "list" && (
                    <form onSubmit={handleSearch} className="flex gap-2">
                        <input value={q} onChange={e => setQ(e.target.value)}
                            placeholder="搜索规范编号或标题..."
                            className="px-3 py-1.5 bg-gray-900 border border-gray-700 rounded-lg text-sm
                                       text-gray-200 outline-none focus:border-indigo-500 placeholder-gray-600 w-56" />
                        <button type="submit"
                            className="px-3 py-1.5 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-500">
                            搜索
                        </button>
                        {search && (
                            <button type="button" onClick={() => { setQ(""); setSearch(""); setPage(1); }}
                                className="px-3 py-1.5 bg-gray-800 text-gray-400 text-sm rounded-lg hover:text-white">
                                清除
                            </button>
                        )}
                    </form>
                )}
            </div>

            {/* 选项卡 */}
            <div className="flex items-center gap-1 border-b border-gray-800 mb-5">
                <button onClick={() => setActiveTab("list")}
                    className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${activeTab === "list" ? "border-indigo-500 text-white" : "border-transparent text-gray-500 hover:text-gray-300"}`}>
                    文档列表
                </button>
                {isAdmin && (
                    <button onClick={() => setActiveTab("reprocess")}
                        className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${activeTab === "reprocess" ? "border-indigo-500 text-white" : "border-transparent text-gray-500 hover:text-gray-300"}`}>
                        重新处理
                    </button>
                )}
            </div>

            {activeTab === "reprocess" && isAdmin && <LibraryReprocessTab />}

            {activeTab === "list" && (
                <>
                    {fetchError && (
                        <div className="px-4 py-3 bg-red-500/10 border border-red-500/30 rounded-lg text-sm text-red-400">
                            加载失败，请刷新页面重试
                        </div>
                    )}
                    {loading ? <SkeletonTable rows={10} /> : !fetchError && (
                        <>
                            <table className="w-full text-sm">
                                <thead>
                                    <tr className="border-b border-gray-800 text-gray-400 text-left">
                                        <th className="pb-3 pr-6">规范编号</th>
                                        <th className="pb-3 pr-6">标题</th>
                                        <th className="pb-3 pr-6">版本</th>
                                        <th className="pb-3 pr-6">发布日期</th>
                                        <th className="pb-3">章节数</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {docs.length === 0 && (
                                        <tr><td colSpan={5} className="py-12 text-center text-sm text-gray-500">
                                            {search ? `未找到与"${search}"相关的文档` : "暂无文档"}
                                        </td></tr>
                                    )}
                                    {docs.map(doc => (
                                        <tr key={doc.doc_id} className="border-b border-gray-800/50">
                                            <td className="py-3 pr-6 font-mono text-indigo-400">
                                                <Link href={`/library/${doc.doc_id}`} className="hover:underline">
                                                    {doc.doc_id}
                                                </Link>
                                            </td>
                                            <td className="py-3 pr-6 text-gray-300">{doc.title ?? "—"}</td>
                                            <td className="py-3 pr-6 text-gray-400">{doc.version ?? "—"}</td>
                                            <td className="py-3 pr-6 text-gray-400">{doc.issue_date ?? "—"}</td>
                                            <td className="py-3 text-gray-400">{doc.section_count}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                            {pages > 1 && (
                                <div className="flex items-center gap-2 mt-6">
                                    <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
                                        className="px-3 py-1.5 bg-gray-900 border border-gray-700 rounded text-sm text-gray-300 hover:border-gray-500 disabled:opacity-40">
                                        上一页
                                    </button>
                                    <span className="text-sm text-gray-500">第 {page} / {pages} 页</span>
                                    <button onClick={() => setPage(p => Math.min(pages, p + 1))} disabled={page === pages}
                                        className="px-3 py-1.5 bg-gray-900 border border-gray-700 rounded text-sm text-gray-300 hover:border-gray-500 disabled:opacity-40">
                                        下一页
                                    </button>
                                </div>
                            )}
                        </>
                    )}
                </>
            )}
        </div>
    );
}
