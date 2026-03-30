"use client";
import { useRef, useEffect, useCallback } from "react";
import { Send, RotateCcw, Paperclip, X } from "lucide-react";
import { Strategy } from "./types";

const strategies: { value: Strategy; label: string }[] = [
    { value: "parallel", label: "并行" },
    { value: "sequential", label: "串行" },
    { value: "graph_augmented", label: "图谱" },
    { value: "multi_hop", label: "多跳" },
];

interface Props {
    value: string;
    strategy: Strategy;
    loading: boolean;
    streaming: boolean;
    historyLen: number;
    pendingImages: string[];
    onChange: (v: string) => void;
    onStrategy: (s: Strategy) => void;
    onSubmit: () => void;
    onClear: () => void;
    onAddImages: (imgs: string[]) => void;
    onRemoveImage: (idx: number) => void;
}

export default function ConversationInput({
    value, strategy, loading, streaming, historyLen, pendingImages,
    onChange, onStrategy, onSubmit, onClear, onAddImages, onRemoveImage,
}: Props) {
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    useEffect(() => { textareaRef.current?.focus(); }, []);

    function handleKeyDown(e: React.KeyboardEvent) {
        if (e.key === "Enter" && !e.shiftKey && !loading && !streaming) {
            e.preventDefault();
            onSubmit();
        }
    }

    const readFilesAsBase64 = useCallback((files: File[]) => {
        const imageFiles = files.filter(f => f.type.startsWith("image/"));
        if (!imageFiles.length) return;
        Promise.all(imageFiles.map(f => new Promise<string>((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result as string);
            reader.onerror = reject;
            reader.readAsDataURL(f);
        }))).then(onAddImages).catch(() => {});
    }, [onAddImages]);

    function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
        if (e.target.files) readFilesAsBase64(Array.from(e.target.files));
        e.target.value = "";
    }

    function handlePaste(e: React.ClipboardEvent) {
        const files = Array.from(e.clipboardData.items)
            .filter(item => item.kind === "file" && item.type.startsWith("image/"))
            .map(item => item.getAsFile())
            .filter(Boolean) as File[];
        if (files.length) readFilesAsBase64(files);
    }

    const canSend = (value.trim() || pendingImages.length > 0) && !loading && !streaming;

    return (
        <div className="border-t border-gray-800 bg-gray-950 px-4 py-4">
            {/* 策略 + 清空 */}
            <div className="flex items-center gap-2 mb-3">
                <div className="flex gap-1 bg-gray-900 border border-gray-800 rounded-lg p-0.5">
                    {strategies.map(s => (
                        <button key={s.value} onClick={() => onStrategy(s.value)}
                            className={`px-2.5 py-1 rounded text-xs transition-colors ${strategy === s.value
                                    ? "bg-indigo-600 text-white"
                                    : "text-gray-500 hover:text-gray-300"
                                }`}>
                            {s.label}
                        </button>
                    ))}
                </div>
                {historyLen > 0 && (
                    <span className="text-xs text-gray-600 ml-1">
                        {Math.floor(historyLen / 2)} 轮对话
                    </span>
                )}
                {historyLen > 0 && (
                    <button onClick={onClear}
                        className="ml-auto flex items-center gap-1 text-xs text-gray-600
                       hover:text-gray-400 transition-colors">
                        <RotateCcw size={11} />
                        清空对话
                    </button>
                )}
            </div>

            {/* 图片预览区 */}
            {pendingImages.length > 0 && (
                <div className="flex flex-wrap gap-2 mb-2 px-1">
                    {pendingImages.map((src, idx) => (
                        <div key={idx} className="relative group">
                            {/* eslint-disable-next-line @next/next/no-img-element */}
                            <img src={src} alt="" className="h-16 w-16 object-cover rounded-lg border border-gray-700" />
                            <button
                                onClick={() => onRemoveImage(idx)}
                                className="absolute -top-1.5 -right-1.5 w-4 h-4 bg-gray-800 border border-gray-600
                                           rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100
                                           transition-opacity hover:bg-red-900">
                                <X size={9} className="text-gray-300" />
                            </button>
                        </div>
                    ))}
                </div>
            )}

            {/* 输入框 */}
            <div className="flex items-end gap-2 bg-gray-900 border border-gray-700
                      rounded-2xl px-3 py-3 focus-within:border-indigo-500 transition-colors">
                {/* 附件按钮 */}
                <button
                    onClick={() => fileInputRef.current?.click()}
                    disabled={loading || streaming}
                    className="w-7 h-7 flex items-center justify-center rounded-lg
                               text-gray-500 hover:text-gray-300 hover:bg-gray-800
                               disabled:opacity-30 transition-colors flex-shrink-0"
                    title="上传图片">
                    <Paperclip size={15} />
                </button>
                <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/*"
                    multiple
                    className="hidden"
                    onChange={handleFileChange}
                />

                <textarea
                    ref={textareaRef}
                    value={value}
                    onChange={e => onChange(e.target.value)}
                    onKeyDown={handleKeyDown}
                    onPaste={handlePaste}
                    placeholder="发送消息或粘贴图片... （Enter 发送，Shift+Enter 换行）"
                    rows={1}
                    className="flex-1 bg-transparent text-gray-200 text-sm resize-none outline-none
                     placeholder-gray-600 max-h-32 leading-relaxed"
                    style={{ height: "auto" }}
                    onInput={e => {
                        const el = e.target as HTMLTextAreaElement;
                        el.style.height = "auto";
                        el.style.height = Math.min(el.scrollHeight, 128) + "px";
                    }}
                />
                <button
                    onClick={onSubmit}
                    disabled={!canSend}
                    className="w-8 h-8 rounded-xl bg-indigo-600 flex items-center justify-center
                     hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed
                     transition-colors flex-shrink-0"
                >
                    <Send size={14} className="text-white" />
                </button>
            </div>
            <div className="text-xs text-gray-700 text-center mt-2">
                CPS 知识库可能存在错误，请以原始规范为准
            </div>
        </div>
    );
}
