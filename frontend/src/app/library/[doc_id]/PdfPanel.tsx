import { FileText, Download, X, Loader2 } from "lucide-react";

interface Props {
    docId:       string;
    pdfUrl:      string;
    pdfLoading:  boolean;
    watermarkUrl: string;
    onLoadStart: () => void;
    onLoad:      () => void;
    onClose:     () => void;
}

export default function PdfPanel({
    docId, pdfUrl, pdfLoading, watermarkUrl, onLoadStart, onLoad, onClose,
}: Props) {
    return (
        <div className="flex flex-col border-l border-gray-800 bg-gray-900" style={{ width: "58%" }}>
            {/* PDF 工具栏 */}
            <div className="shrink-0 flex items-center gap-3 px-4 py-2.5 border-b border-gray-800 bg-gray-950">
                <FileText size={14} className="text-gray-500 shrink-0" />
                <span className="text-xs text-gray-400 truncate flex-1 font-mono">
                    {docId} — 原文 PDF
                </span>
                <a href={pdfUrl} download
                    className="p-1.5 rounded text-gray-500 hover:text-white hover:bg-gray-800 transition-colors"
                    title="下载 PDF">
                    <Download size={13} />
                </a>
                <button
                    onClick={onClose}
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
            </div>
        </div>
    );
}
