"use client";

import { useEffect, useState } from "react";
import { FileText, Download, X, Loader2, AlertTriangle } from "lucide-react";

interface Props {
    docId:        string;
    pdfUrl:       string;
    pdfLoading:   boolean;
    watermarkUrl: string;
    canDownload:  boolean;
    anchorPage?:  number;
    onDownload:   () => void;
    onLoadStart:  () => void;
    onLoad:       () => void;
    onClose:      () => void;
}

export default function PdfPanel({
    docId, pdfUrl, pdfLoading, watermarkUrl, canDownload, onDownload, onLoadStart, onLoad, onClose,
}: Props) {
    const [previewError, setPreviewError] = useState<string | null>(null);
    const [checking,     setChecking]     = useState(true);

    // 在渲染 iframe 前先检查预览 URL 是否可访问，
    // 避免 4xx/5xx 在 iframe 内无声地显示为空白页。
    // 使用 GET + AbortController（部分 Next.js 代理不支持 HEAD）。
    useEffect(() => {
        setPreviewError(null);
        setChecking(true);
        const ctrl = new AbortController();
        fetch(pdfUrl, { signal: ctrl.signal })
            .then(res => {
                ctrl.abort(); // 收到响应头后立即中止正文传输
                if (!res.ok) {
                    const msg: Record<number, string> = {
                        404: "原文文件未找到，请确认文档已上传。",
                        401: "无访问权限，请重新登录。",
                        503: "DOC/DOCX 在线预览需要 LibreOffice，服务器暂未安装。请点击「下载原文」后本地查看，或联系管理员安装 LibreOffice。",
                    };
                    setPreviewError(msg[res.status] ?? `预览失败（HTTP ${res.status}），请下载原文后本地查看。`);
                }
            })
            .catch(err => {
                if (err.name !== "AbortError") {
                    setPreviewError("无法连接到服务器，请检查网络。");
                }
            })
            .finally(() => setChecking(false));
        return () => ctrl.abort();
    }, [pdfUrl]);

    return (
        <div className="flex flex-col border-l border-gray-800 bg-gray-900" style={{ width: "58%" }}>
            {/* 工具栏 */}
            <div className="shrink-0 flex items-center gap-3 px-4 py-2.5 border-b border-gray-800 bg-gray-950">
                <FileText size={14} className="text-gray-500 shrink-0" />
                <span className="text-xs text-gray-400 truncate flex-1 font-mono">
                    {docId} — 原文预览
                </span>
                {canDownload && (
                    <button
                        onClick={onDownload}
                        className="p-1.5 rounded text-gray-500 hover:text-white hover:bg-gray-800 transition-colors"
                        title="下载原文"
                    >
                        <Download size={13} />
                    </button>
                )}
                <button
                    onClick={onClose}
                    className="p-1.5 rounded text-gray-500 hover:text-white hover:bg-gray-800 transition-colors"
                    title="关闭预览"
                >
                    <X size={14} />
                </button>
            </div>

            {/* 内容区 */}
            <div className="relative flex-1">
                {(checking || pdfLoading) && !previewError && (
                    <div className="absolute inset-0 flex items-center justify-center bg-gray-900 z-10">
                        <Loader2 size={24} className="animate-spin text-gray-600" />
                    </div>
                )}

                {previewError ? (
                    <div className="flex flex-col items-center justify-center h-full gap-4 px-8 text-center">
                        <AlertTriangle size={32} className="text-amber-500 shrink-0" />
                        <div className="text-sm text-gray-300 leading-relaxed">{previewError}</div>
                        {canDownload && (
                            <button
                                onClick={onDownload}
                                className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500
                                           text-white text-sm rounded-lg transition-colors"
                            >
                                <Download size={14} />
                                下载原文
                            </button>
                        )}
                    </div>
                ) : !checking && (
                    <>
                        <iframe
                            src={`${pdfUrl}#toolbar=1&view=FitH${anchorPage !== undefined ? `&page=${anchorPage + 1}` : ""}`}
                            className="w-full h-full border-0"
                            title={`${docId} PDF 预览`}
                            onLoadStart={onLoadStart}
                            onLoad={onLoad}
                        />
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
                    </>
                )}
            </div>
        </div>
    );
}
