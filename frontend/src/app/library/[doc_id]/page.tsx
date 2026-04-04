"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { fetchApi } from "@/lib/api";
import { ArrowLeft, FileText, X, Download, ChevronDown, ChevronUp, Loader2 } from "lucide-react";

interface UserInfo { username: string; full_name: string; department: string; }

/** 从 localStorage 读取当前用户信息 */
function getCurrentUser(): UserInfo | null {
    try {
        const raw = localStorage.getItem("user");
        return raw ? JSON.parse(raw) : null;
    } catch {
        return null;
    }
}

/** 生成重复水印的 SVG data-URI（每块 280×140，旋转 -30°） */
function buildWatermarkUrl(name: string, time: string): string {
    const svg = `
<svg xmlns="http://www.w3.org/2000/svg" width="280" height="140">
  <g transform="rotate(-30 140 70)" opacity="0.13" fill="#94a3b8"
     font-family="PingFang SC, Hiragino Sans GB, Microsoft YaHei, sans-serif" text-anchor="middle">
    <text x="140" y="58"  font-size="15" font-weight="600">${name}</text>
    <text x="140" y="82"  font-size="11">${time}</text>
  </g>
</svg>`.trim();
    return `url("data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}")`;
}

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
    const idx = text.toLowerCase().indexOf(keyword.toLowerCase());
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
    const docId  = params.doc_id as string;

    const [doc,            setDoc]           = useState<DocumentDetail | null>(null);
    const [expandedChunk,  setExpandedChunk] = useState<string | null>(null);
    const [sectionContent, setSectionContent] = useState<Record<string, SectionContent>>({});
    const [loadingChunk,   setLoadingChunk]  = useState<string | null>(null);
    const [sectionSearch,  setSectionSearch] = useState("");
    const [pdfUrl,         setPdfUrl]        = useState<string | null>(null);
    const [showPdf,        setShowPdf]       = useState(false);
    const [pdfLoading,     setPdfLoading]    = useState(false);
    const [watermarkUrl,   setWatermarkUrl]  = useState("");

    useEffect(() => {
        if (!docId) return;
        fetchApi<DocumentDetail>(`/api/documents/${docId}`).then(setDoc).catch(() => {});

        // 尝试获取 PDF 静态地址（文件不存在时静默失败）
        fetchApi<{ url: string }>(`/api/documents/${docId}/pdf-url`)
            .then(data => setPdfUrl(`http://localhost:8000${data.url}`))
            .catch(() => {});

        // 构建水印（用户名 + 当前时间）
        const user = getCurrentUser();
        const name = user?.full_name || user?.username || "未知用户";
        const time = new Date().toLocaleString("zh-CN", {
            year: "numeric", month: "2-digit", day: "2-digit",
            hour: "2-digit", minute: "2-digit",
        });
        setWatermarkUrl(buildWatermarkUrl(name, time));
    }, [docId]);

    async function toggleSection(chunkId: string) {
        if (expandedChunk === chunkId) { setExpandedChunk(null); return; }
        if (sectionContent[chunkId])  { setExpandedChunk(chunkId); return; }
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
        return (
            <div className="flex items-center justify-center h-full text-gray-500 text-sm gap-2">
                <Loader2 size={16} className="animate-spin" />
                加载中...
            </div>
        );
    }

    const visibleSections = sectionSearch
        ? doc.sections.filter(s =>
            s.title.toLowerCase().includes(sectionSearch.toLowerCase()) ||
            s.number.includes(sectionSearch)
          )
        : doc.sections;

    // ── 文档信息面板（左侧或全宽）────────────────────────────────────────────
    const docPanel = (
        <div className={`bg-gray-950 overflow-y-auto ${showPdf ? "flex-1 min-w-0" : "p-8 max-w-3xl min-h-screen"}`}>
            <div className={showPdf ? "px-6 pt-5 pb-4" : "mb-6"}>
                <a
                    href="/library"
                    className="inline-flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-300 transition-colors"
                >
                    <ArrowLeft size={14} />
                    返回文档库
                </a>
            </div>

            {/* 标题区 */}
            <div className={showPdf ? "px-6 pb-4 border-b border-gray-800" : "mb-8"}>
                <div className="text-sm font-mono text-indigo-400 mb-1">
                    {doc.doc_id} · 版本 {doc.version || "—"}
                </div>
                <h1 className="text-xl font-semibold text-white leading-snug">
                    {doc.title || "未命名文档"}
                </h1>
                <div className="text-sm text-gray-500 mt-1">
                    发布日期：{doc.issue_date || "—"}
                </div>

                {/* 操作按钮行 */}
                <div className="flex items-center gap-2 mt-3">
                    {pdfUrl ? (
                        <button
                            onClick={() => setShowPdf(v => !v)}
                            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                                showPdf
                                    ? "bg-indigo-600 text-white hover:bg-indigo-700"
                                    : "bg-gray-800 text-gray-300 hover:bg-gray-700 hover:text-white border border-gray-700"
                            }`}
                        >
                            <FileText size={13} />
                            {showPdf ? "关闭预览" : "预览原文 PDF"}
                        </button>
                    ) : (
                        <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs
                                         text-gray-600 border border-gray-800 cursor-default"
                              title="PDF 文件未找到，请先上传">
                            <FileText size={13} />
                            原文暂无
                        </span>
                    )}
                    {pdfUrl && (
                        <a
                            href={pdfUrl}
                            download
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs
                                       bg-gray-800 text-gray-400 hover:text-white hover:bg-gray-700
                                       border border-gray-700 transition-colors"
                        >
                            <Download size={13} />
                            下载
                        </a>
                    )}
                </div>
            </div>

            {/* 引用文件 */}
            {doc.refs.length > 0 && (
                <div className={showPdf ? "px-6 py-4 border-b border-gray-800" : "mb-8"}>
                    <div className="text-xs text-gray-500 uppercase tracking-wider mb-2">引用文件</div>
                    <div className="flex flex-wrap gap-2">
                        {doc.refs.map(ref => (
                            <a key={ref} href={`/library/${ref}`}
                                className="px-3 py-1 bg-gray-900 border border-gray-700 rounded-md
                                           text-sm font-mono text-indigo-400 hover:border-indigo-500 transition-colors">
                                {ref}
                            </a>
                        ))}
                    </div>
                </div>
            )}

            {/* 章节列表 */}
            <div className={showPdf ? "px-6 py-4" : ""}>
                <div className="flex items-center justify-between mb-3">
                    <div className="text-xs text-gray-500 uppercase tracking-wider">
                        章节目录 · {doc.sections.length} 个
                        {sectionSearch && ` · 匹配 ${visibleSections.length} 个`}
                    </div>
                    <input
                        value={sectionSearch}
                        onChange={e => setSectionSearch(e.target.value)}
                        placeholder="搜索章节..."
                        className="px-2.5 py-1 bg-gray-900 border border-gray-700 rounded
                                   text-xs text-gray-200 outline-none focus:border-indigo-500
                                   placeholder-gray-500 w-36"
                    />
                </div>

                <div className="space-y-0.5">
                    {visibleSections.map(section => {
                        const isExpanded = expandedChunk === section.chunk_id;
                        const isLoading  = loadingChunk  === section.chunk_id;
                        const content    = sectionContent[section.chunk_id];
                        return (
                            <div key={section.chunk_id}>
                                <button
                                    onClick={() => toggleSection(section.chunk_id)}
                                    className="w-full flex items-baseline gap-3 px-3 py-2.5
                                               rounded-lg hover:bg-gray-900 transition-colors text-left group"
                                >
                                    <span className="text-xs font-mono text-gray-500 w-12 shrink-0">
                                        {section.number}
                                    </span>
                                    <span className="text-sm text-gray-300 flex-1 min-w-0">
                                        {highlight(section.title, sectionSearch)}
                                    </span>
                                    <span className="text-gray-600 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                                        {isLoading
                                            ? <Loader2 size={12} className="animate-spin" />
                                            : isExpanded
                                                ? <ChevronUp size={12} />
                                                : <ChevronDown size={12} />
                                        }
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
        </div>
    );

    // ── PDF 预览面板（右侧）──────────────────────────────────────────────────
    const pdfPanel = showPdf && pdfUrl && (
        <div className="flex flex-col border-l border-gray-800 bg-gray-900" style={{ width: "58%" }}>
            {/* PDF 工具栏 */}
            <div className="shrink-0 flex items-center gap-3 px-4 py-2.5 border-b border-gray-800 bg-gray-950">
                <FileText size={14} className="text-gray-500 shrink-0" />
                <span className="text-xs text-gray-400 truncate flex-1 font-mono">
                    {doc.doc_id} — 原文 PDF
                </span>
                <a href={pdfUrl} download
                    className="p-1.5 rounded text-gray-500 hover:text-white hover:bg-gray-800 transition-colors"
                    title="下载 PDF">
                    <Download size={13} />
                </a>
                <button
                    onClick={() => setShowPdf(false)}
                    className="p-1.5 rounded text-gray-500 hover:text-white hover:bg-gray-800 transition-colors"
                    title="关闭预览"
                >
                    <X size={14} />
                </button>
            </div>

            {/* iframe + 水印覆盖层 */}
            <div className="relative flex-1">
                {pdfLoading && (
                    <div className="absolute inset-0 flex items-center justify-center bg-gray-900 z-10">
                        <Loader2 size={24} className="animate-spin text-gray-600" />
                    </div>
                )}
                <iframe
                    src={`${pdfUrl}#toolbar=1&view=FitH`}
                    className="w-full h-full border-0"
                    title={`${doc.doc_id} PDF 预览`}
                    onLoadStart={() => setPdfLoading(true)}
                    onLoad={() => setPdfLoading(false)}
                />
                {/* 水印：pointer-events:none 不影响 PDF 交互 */}
                {watermarkUrl && (
                    <div
                        className="absolute inset-0 pointer-events-none z-20"
                        style={{
                            backgroundImage:  watermarkUrl,
                            backgroundRepeat: "repeat",
                            backgroundSize:   "280px 140px",
                        }}
                    />
                )}
            </div>
        </div>
    );

    // ── 整体布局 ─────────────────────────────────────────────────────────────
    if (showPdf) {
        return (
            <div className="flex h-full overflow-hidden">
                <div className="flex flex-col overflow-hidden" style={{ width: "42%" }}>
                    {docPanel}
                </div>
                {pdfPanel}
            </div>
        );
    }

    return docPanel;
}
