"use client";

import { useEffect, useState, useRef } from "react";
import { Download, Loader2, AlertTriangle, X, FileText, ChevronDown } from "lucide-react";

interface Props {
    docId:       string;
    rawUrl:      string;
    canDownload: boolean;
    onDownload:  () => void;
    onClose:     () => void;
}

// 目录段落特征：行尾是"...数字"（页码引导点）或"全角空格+数字"
const TOC_LINE_RE = /[.…·\u3000]{3,}\s*\d+\s*$|\s{4,}\d+\s*$/;

function isTocBlock(text: string): boolean {
    const lines = text.split("\n").map(l => l.trim()).filter(Boolean);
    if (lines.length === 0) return false;
    const hits = lines.filter(l => TOC_LINE_RE.test(l)).length;
    return hits / lines.length >= 0.5;
}

interface NavEntry { id: string; text: string; level: number; }

// 解析已渲染 HTML，给 h1-h4 注入递增 id 并返回导航条目
function processHtml(rawHtml: string): { html: string; nav: NavEntry[] } {
    const nav: NavEntry[] = [];
    let idx = 0;
    const html = rawHtml.replace(/<(h[1-4])(\s[^>]*)?>(.+?)<\/h[1-4]>/gi, (_m, tag, attrs, inner) => {
        const id  = `dh${idx++}`;
        const lvl = parseInt(tag[1], 10);
        const txt = inner.replace(/<[^>]+>/g, "").trim();
        if (txt) nav.push({ id, text: txt, level: lvl });
        return `<${tag} id="${id}"${attrs ?? ""}>${inner}</${tag}>`;
    });
    return { html, nav };
}

const STYLE_MAP = [
    "p[style-name='Heading 1'] => h1:fresh",
    "p[style-name='Heading 2'] => h2:fresh",
    "p[style-name='Heading 3'] => h3:fresh",
    "p[style-name='Heading 4'] => h4:fresh",
    "p[style-name='标题 1']    => h1:fresh",
    "p[style-name='标题 2']    => h2:fresh",
    "p[style-name='标题 3']    => h3:fresh",
    "p[style-name='标题 4']    => h4:fresh",
];

export default function DocxViewer({ docId, rawUrl, canDownload, onDownload, onClose }: Props) {
    const [html,    setHtml]    = useState<string | null>(null);
    const [loading, setLoading] = useState(true);
    const [error,   setError]   = useState<string | null>(null);
    const [nav,     setNav]     = useState<NavEntry[]>([]);
    const [navOpen, setNavOpen] = useState(false);
    const bodyRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        setHtml(null); setError(null); setLoading(true); setNav([]);
        let cancelled = false;

        (async () => {
            try {
                const res = await fetch(rawUrl);
                if (!res.ok) {
                    const msgs: Record<number, string> = {
                        404: "原文文件未找到，请确认文档已上传。",
                        401: "无访问权限，请重新登录。",
                    };
                    setError(msgs[res.status] ?? `加载失败（HTTP ${res.status}）`);
                    return;
                }
                const buf = await res.arrayBuffer();
                if (cancelled) return;

                // Dynamic import keeps server bundle clean
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                const mammoth = await import("mammoth") as any;
                const result: { value: string } = await mammoth.convertToHtml(
                    { arrayBuffer: buf },
                    { styleMap: STYLE_MAP },
                );
                if (cancelled) return;

                // Strip TOC paragraphs
                const parser  = new DOMParser();
                const doc     = parser.parseFromString(result.value, "text/html");
                doc.querySelectorAll("p").forEach(p => {
                    if (isTocBlock(p.textContent ?? "")) p.remove();
                });

                const { html: finalHtml, nav: entries } = processHtml(doc.body.innerHTML);
                if (!cancelled) { setHtml(finalHtml); setNav(entries); }
            } catch (e) {
                if (!cancelled) setError(`文档解析失败：${(e as Error).message}`);
            } finally {
                if (!cancelled) setLoading(false);
            }
        })();
        return () => { cancelled = true; };
    }, [rawUrl]);

    function jumpTo(id: string) {
        setNavOpen(false);
        bodyRef.current?.querySelector(`#${id}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
    }

    return (
        <div className="flex flex-col border-l border-gray-800 bg-gray-900" style={{ width: "58%" }}>
            {/* 工具栏 */}
            <div className="shrink-0 flex items-center gap-2 px-4 py-2.5 border-b border-gray-800 bg-gray-950">
                <FileText size={14} className="text-gray-500 shrink-0" />
                <span className="text-xs text-gray-400 truncate flex-1 font-mono">
                    {docId} — DOCX 在线预览
                </span>

                {/* 章节导航下拉 */}
                {nav.length > 0 && (
                    <div className="relative">
                        <button
                            onClick={() => setNavOpen(v => !v)}
                            className="flex items-center gap-1 px-2 py-1 rounded text-xs
                                       text-gray-400 hover:text-white bg-gray-800 border border-gray-700"
                        >
                            章节导航 <ChevronDown size={11} />
                        </button>
                        {navOpen && (
                            <div
                                className="absolute right-0 top-full mt-1 z-50 w-72 max-h-80 overflow-y-auto
                                           bg-gray-900 border border-gray-700 rounded-lg shadow-2xl"
                                onMouseLeave={() => setNavOpen(false)}
                            >
                                {nav.map(entry => (
                                    <button
                                        key={entry.id}
                                        onClick={() => jumpTo(entry.id)}
                                        className="w-full text-left px-3 py-1.5 text-xs text-gray-300
                                                   hover:bg-gray-800 hover:text-white truncate"
                                        style={{ paddingLeft: `${(entry.level - 1) * 12 + 12}px` }}
                                    >
                                        {entry.text}
                                    </button>
                                ))}
                            </div>
                        )}
                    </div>
                )}

                {canDownload && (
                    <button onClick={onDownload}
                        className="p-1.5 rounded text-gray-500 hover:text-white hover:bg-gray-800 transition-colors"
                        title="下载原文">
                        <Download size={13} />
                    </button>
                )}
                <button onClick={onClose}
                    className="p-1.5 rounded text-gray-500 hover:text-white hover:bg-gray-800 transition-colors"
                    title="关闭预览">
                    <X size={14} />
                </button>
            </div>

            {/* 内容区 */}
            <div ref={bodyRef} className="relative flex-1 overflow-y-auto">
                {loading && (
                    <div className="absolute inset-0 flex items-center justify-center bg-gray-900 z-10">
                        <Loader2 size={24} className="animate-spin text-gray-600" />
                    </div>
                )}
                {error && (
                    <div className="flex flex-col items-center justify-center h-full gap-4 px-8 text-center">
                        <AlertTriangle size={32} className="text-amber-500 shrink-0" />
                        <div className="text-sm text-gray-300 leading-relaxed">{error}</div>
                        {canDownload && (
                            <button onClick={onDownload}
                                className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500
                                           text-white text-sm rounded-lg transition-colors">
                                <Download size={14} /> 下载原文
                            </button>
                        )}
                    </div>
                )}
                {html !== null && !error && (
                    <div
                        className="
                            p-8 text-[14px] leading-7 text-gray-300
                            [&_h1]:text-xl [&_h1]:font-bold [&_h1]:text-white
                                [&_h1]:mt-8 [&_h1]:mb-3 [&_h1]:pb-2
                                [&_h1]:border-b [&_h1]:border-gray-700
                            [&_h2]:text-lg [&_h2]:font-semibold [&_h2]:text-white
                                [&_h2]:mt-6 [&_h2]:mb-2
                            [&_h3]:text-base [&_h3]:font-semibold [&_h3]:text-gray-100
                                [&_h3]:mt-5 [&_h3]:mb-1
                            [&_h4]:text-sm [&_h4]:font-semibold [&_h4]:text-gray-200
                                [&_h4]:mt-4 [&_h4]:mb-1
                            [&_p]:mb-3
                            [&_ul]:list-disc [&_ul]:pl-6 [&_ul]:mb-3
                            [&_ol]:list-decimal [&_ol]:pl-6 [&_ol]:mb-3
                            [&_li]:mb-1
                            [&_strong]:text-gray-100 [&_strong]:font-semibold
                            [&_table]:w-full [&_table]:border-collapse [&_table]:my-4 [&_table]:text-sm
                            [&_td]:border [&_td]:border-gray-600 [&_td]:px-3 [&_td]:py-2 [&_td]:align-top
                            [&_th]:border [&_th]:border-gray-600 [&_th]:px-3 [&_th]:py-2
                                [&_th]:bg-gray-800 [&_th]:font-semibold [&_th]:text-gray-200
                            [&_img]:max-w-full [&_img]:rounded [&_img]:my-2
                        "
                        // biome-ignore lint/security/noDangerouslySetInnerHtml: mammoth output is sanitized DOCX content
                        dangerouslySetInnerHTML={{ __html: html }}
                    />
                )}
            </div>
        </div>
    );
}
