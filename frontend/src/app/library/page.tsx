import { Suspense } from "react";
import SkeletonTable from "@/components/ui/SkeletonTable";
import Link from "next/link";

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

async function getDocuments(page: number): Promise<PagedResponse> {
    const res = await fetch(
        `http://localhost:8000/api/documents?page=${page}&per_page=20`,
        { cache: "no-store" }
    );
    return res.json();
}

async function LibraryTable({ page }: { page: number }) {
    const { data: documents, total, pages } = await getDocuments(page);

    return (
        <div className="p-8 max-w-4xl">
            <h1 className="text-2xl font-semibold text-white mb-6">
                文档库
                <span className="ml-3 text-sm text-gray-400 font-normal">
                    {total} 个文档
                </span>
            </h1>

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
                    {documents.map((doc) => (
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

            {/* 分页控件 */}
            {pages > 1 && (
                <div className="flex items-center gap-2 mt-6">
                    {page > 1 && (
                        <Link
                            href={`/library?page=${page - 1}`}
                            className="px-3 py-1.5 bg-gray-900 border border-gray-700
                         rounded text-sm text-gray-300 hover:border-gray-500"
                        >
                            上一页
                        </Link>
                    )}
                    <span className="text-sm text-gray-500">
                        第 {page} / {pages} 页
                    </span>
                    {page < pages && (
                        <Link
                            href={`/library?page=${page + 1}`}
                            className="px-3 py-1.5 bg-gray-900 border border-gray-700
                         rounded text-sm text-gray-300 hover:border-gray-500"
                        >
                            下一页
                        </Link>
                    )}
                </div>
            )}
        </div>
    );
}

export default async function LibraryPage({
    searchParams,
}: {
    searchParams: Promise<{ page?: string }>;
}) {
    const { page: pageStr } = await searchParams;
    const page = Math.max(1, parseInt(pageStr ?? "1", 10) || 1);

    return (
        <Suspense fallback={<SkeletonTable rows={20} />}>
            <LibraryTable page={page} />
        </Suspense>
    );
}