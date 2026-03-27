import { Suspense } from "react";
import SkeletonTable from "@/components/ui/SkeletonTable";

interface Document {
    doc_id: string;
    title: string | null;
    version: string | null;
    issue_date: string | null;
    section_count: number;
}

async function getDocuments(): Promise<Document[]> {
    const res = await fetch("http://localhost:8000/api/documents", {
        cache: "no-store", // 每次请求都获取最新数据
    });
    return res.json();
}

async function LibraryTable() {
    const documents = await getDocuments();
    return (
        <div className="p-8 min-h-screen bg-gray-950">
            <h1 className="text-2xl font-semibold text-white mb-6">
                文档库
                <span className="ml-3 text-sm text-gray-400 font-normal">
                    {documents.length} 个文档
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
                                <a href={`/library/${doc.doc_id}`}
                                    className="hover:underline">
                                    {doc.doc_id}
                                </a>
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
                            <td className="py-3 text-gray-400">
                                {doc.section_count}
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    )
}

export default function LibraryPage() {
    return (
        <Suspense fallback={<SkeletonTable rows={6} />}>
            <LibraryTable />
        </Suspense>
    );
}