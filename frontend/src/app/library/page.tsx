"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import SkeletonTable from "@/components/ui/SkeletonTable";

interface Document {
    doc_id: string;
    title: string | null;
    version: string | null;
    issue_date: string | null;
    section_count: number;
}

interface PagedResponse {
    data: Document[];
    total: number;
    page: number;
    per_page: number;
    pages: number;
}

export default function LibraryPage() {
    const [docs, setDocs] = useState<Document[]>([]);
    const [total, setTotal] = useState(0);
    const [pages, setPages] = useState(1);
    const [page, setPage] = useState(1);
    const [q, setQ] = useState("");
    const [search, setSearch] = useState("");
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        setLoading(true);
        const params = new URLSearchParams({
            page: String(page),
            per_page: "20",
            q: search,
        });
        fetch(`/api/documents?${params}`)
            .then(r => r.json())
            .then((data: PagedResponse) => {
                setDocs(data.data);
                setTotal(data.total);
                setPages(data.pages);
                setLoading(false);
            });
    }, [page, search]);

    function handleSearch(e: React.FormEvent) {
        e.preventDefault();
        setPage(1);
        setSearch(q);
    }

    return (
        <div className="p-8 max-w-4xl min-h-screen bg-gray-950">
            <div className="flex items-center justify-between mb-6">
                <h1 className="text-2xl font-semibold text-white">
                    文档库
                    <span className="ml-3 text-sm text-gray-400 font-normal">
                        {total} 个文档
                    </span>
                </h1>

                {/* 搜索框 */}
                <form onSubmit={handleSearch} className="flex gap-2">
                    <input
                        value={q}
                        onChange={e => setQ(e.target.value)}
                        placeholder="搜索规范编号或标题..."
                        className="px-3 py-1.5 bg-gray-900 border border-gray-700
                       rounded-lg text-sm text-gray-200 outline-none
                       focus:border-indigo-500 placeholder-gray-600 w-56"
                    />
                    <button
                        type="submit"
                        className="px-3 py-1.5 bg-indigo-600 text-white text-sm
                       rounded-lg hover:bg-indigo-500"
                    >
                        搜索
                    </button>
                    {search && (
                        <button
                            type="button"
                            onClick={() => { setQ(""); setSearch(""); setPage(1); }}
                            className="px-3 py-1.5 bg-gray-800 text-gray-400 text-sm
                         rounded-lg hover:text-white"
                        >
                            清除
                        </button>
                    )}
                </form>
            </div>

            {loading ? (
                <SkeletonTable rows={10} />
            ) : (
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

                    {/* 分页 */}
                    {pages > 1 && (
                        <div className="flex items-center gap-2 mt-6">
                            <button
                                onClick={() => setPage(p => Math.max(1, p - 1))}
                                disabled={page === 1}
                                className="px-3 py-1.5 bg-gray-900 border border-gray-700
                           rounded text-sm text-gray-300 hover:border-gray-500
                           disabled:opacity-40"
                            >
                                上一页
                            </button>
                            <span className="text-sm text-gray-500">
                                第 {page} / {pages} 页
                            </span>
                            <button
                                onClick={() => setPage(p => Math.min(pages, p + 1))}
                                disabled={page === pages}
                                className="px-3 py-1.5 bg-gray-900 border border-gray-700
                           rounded text-sm text-gray-300 hover:border-gray-500
                           disabled:opacity-40"
                            >
                                下一页
                            </button>
                        </div>
                    )}
                </>
            )}
        </div>
    );
}