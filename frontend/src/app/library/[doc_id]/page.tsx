"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { fetchApi } from "@/lib/api";
import { ArrowLeft } from "lucide-react";

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

interface SectionContent {
    number: string;
    title: string;
    content: string;
}

function highlight(text: string, keyword: string) {
    if (!keyword) return <>{text}</>;
    const idx = text.indexOf(keyword);
    if (idx === -1) return <>{text}</>;
    return (
        <>
            {text.slice(0, idx)}
            <mark className="bg-indigo-500/30 text-indigo-300 rounded px-0.5">
                {text.slice(idx, idx + keyword.length)}
            </mark>
            {text.slice(idx + keyword.length)}
        </>
    );
}

export default function DocumentDetailPage() {
    const params = useParams();
    const docId = params.doc_id as string;

    const [doc, setDoc] = useState<DocumentDetail | null>(null);
    const [expandedChunk, setExpandedChunk] = useState<string | null>(null);
    const [sectionContent, setSectionContent] = useState<Record<string, SectionContent>>({});
    const [loadingChunk, setLoadingChunk] = useState<string | null>(null);
    const [sectionSearch, setSectionSearch] = useState("");

    useEffect(() => {
        fetchApi<DocumentDetail>(`/api/documents/${docId}`).then(setDoc);
    }, [docId]);

    async function toggleSection(chunkId: string) {
        if (expandedChunk === chunkId) { setExpandedChunk(null); return; }
        if (sectionContent[chunkId]) { setExpandedChunk(chunkId); return; }
        setLoadingChunk(chunkId);
        try {
            const data = await fetchApi<SectionContent>(`/api/sections/${chunkId}`);
            setSectionContent(prev => ({ ...prev, [chunkId]: data }));
            setExpandedChunk(chunkId);
        } finally {
            setLoadingChunk(null);
        }
    }

    if (!doc) {
        return <div className="p-8 text-gray-500 text-sm">加载中...</div>;
    }

    // visibleSections 放在 return 之前，if (!doc) 之后
    const visibleSections = sectionSearch
        ? doc.sections.filter(s =>
            s.title.includes(sectionSearch) || s.number.includes(sectionSearch)
        )
        : doc.sections;

    return (
        <div className="p-8 max-w-3xl min-h-screen bg-gray-950">
            <div className="mb-6">
                <a
                    href="/library"
                    className="inline-flex items-center gap-1.5 text-xs text-gray-500
               hover:text-gray-300 transition-colors"
                >
                    <ArrowLeft size={14} />
                    返回文档库
                </a>
            </div>
            <div className="mb-8">
                <div className="text-sm font-mono text-indigo-400 mb-1">
                    {doc.doc_id} · 版本 {doc.version ?? "—"}
                </div>
                <h1 className="text-2xl font-semibold text-white">
                    {doc.title ?? "未命名文档"}
                </h1>
                <div className="text-sm text-gray-500 mt-1">
                    发布日期：{doc.issue_date ?? "—"}
                </div>
            </div>

            {
                doc.refs.length > 0 && (
                    <div className="mb-8">
                        <div className="text-xs text-gray-500 uppercase tracking-wider mb-2">
                            引用文件
                        </div>
                        <div className="flex flex-wrap gap-2">
                            {doc.refs.map(ref => (
                                <a
                                    key={ref}
                                    href={`/library/${ref}`}
                                    className="px-3 py-1 bg-gray-900 border border-gray-700 rounded-md
                           text-sm font-mono text-indigo-400 hover:border-indigo-500
                           transition-colors"
                                >
                                    {ref}
                                </a>
                            ))}
                        </div>
                    </div>
                )
            }

            <div>
                <div className="flex items-center justify-between mb-3">
                    <div className="text-xs text-gray-500 uppercase tracking-wider">
                        章节目录 · {doc.sections.length} 个章节
                        {sectionSearch && ` · 匹配 ${visibleSections.length} 个`}
                    </div>
                    <input
                        value={sectionSearch}
                        onChange={e => setSectionSearch(e.target.value)}
                        placeholder="搜索章节..."
                        className="px-2.5 py-1 bg-gray-900 border border-gray-700
                       rounded text-xs text-gray-200 outline-none
                       focus:border-indigo-500 placeholder-gray-500 w-36"
                    />
                </div>

                <div className="space-y-1">
                    {visibleSections.map(section => {
                        const isExpanded = expandedChunk === section.chunk_id;
                        const isLoading = loadingChunk === section.chunk_id;
                        const content = sectionContent[section.chunk_id];
                        return (
                            <div key={section.chunk_id}>
                                <button
                                    onClick={() => toggleSection(section.chunk_id)}
                                    className="w-full flex items-baseline gap-3 px-3 py-2.5
                             rounded-lg hover:bg-gray-900 transition-colors text-left"
                                >
                                    <span className="text-xs font-mono text-gray-500 w-12 flex-shrink-0">
                                        {section.number}
                                    </span>
                                    <span className="text-sm text-gray-300 flex-1">
                                        {highlight(section.title, sectionSearch)}
                                    </span>
                                    <span className="text-xs text-gray-600 flex-shrink-0">
                                        {isLoading ? "…" : isExpanded ? "▲" : "▼"}
                                    </span>
                                </button>
                                {isExpanded && content && (
                                    <div className="mx-3 mb-2 px-4 py-3 bg-gray-900 rounded-lg
                                  border border-gray-800 text-sm text-gray-400
                                  leading-relaxed whitespace-pre-wrap">
                                        {content.content}
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>
            </div>

        </div >
    );
}