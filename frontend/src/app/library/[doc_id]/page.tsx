interface Section {
    number: string;
    title: string;
    chunk_id: string;
}

interface DocumentDetail {
    doc_id: string;
    title: string;
    version: string;
    issue_date: string;
    sections: Section[];
    refs: string[];
}

async function getDocument(docId: string): Promise<DocumentDetail> {
    const res = await fetch(
        `http://localhost:8000/api/documents/${docId}`,
        { cache: "no-store" }
    );
    if (!res.ok) throw new Error("文档不存在");
    return res.json();
}

export default async function DocumentDetailPage({
    params,
}: {
    params: { doc_id: string }
}) {
    const { doc_id } = await params;
    const doc = await getDocument(doc_id);

    return (
        <div className="p-8 max-w-3xl">
            {/* 文档头部 */}
            <div className="mb-8">
                <div className="text-sm font-mono text-indigo-400 mb-1">
                    {doc.doc_id}  ·  版本 {doc.version ?? "—"}
                </div>
                <h1 className="text-2xl font-semibold text-white">
                    {doc.title ?? "未命名文档"}
                </h1>
                <div className="text-sm text-gray-500 mt-1">
                    发布日期：{doc.issue_date ?? "—"}
                </div>
            </div>

            {/* 引用文件 */}
            {
                doc.refs.length > 0 && (
                    <div className="mb-8">
                        <div className="text-xs text-gray-500 uppercase tracking-wider mb-2">
                            引用文件
                        </div>
                        <div className="flex flex-wrap gap-2">
                            {
                                doc.refs.map(ref => (
                                    <a
                                        key={ref}
                                        href={`/library/${ref}`}
                                        className="px-3 py-1 bg-gray-900 border border-gray-700
                                                    rounded-md text-sm font-mono text-indigo-400
                                                    hover:border-indigo-500 transition-colors"
                                    >
                                        {ref}
                                    </a>
                                ))
                            }
                        </div>
                    </div>
                )}
            {/* 章节列表 */}
            <div>
                <div className="text-xs text-gray-500 uppercase tracking-wider mb-3">
                    章节目录 · {doc.sections.length} 个章节
                </div>
                <div className="space-y-1">
                    {doc.sections.map(section => (
                        <div
                            key={section.chunk_id}
                            className="flex items-baseline gap-3 px-3 py-2
                         rounded-lg hover:bg-gray-900 transition-colors"
                        >
                            <span className="text-xs font-mono text-gray-500 w-12 flex-shrink-0">
                                {section.number}
                            </span>
                            <span className="text-sm text-gray-300">
                                {section.title}
                            </span>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    )
}