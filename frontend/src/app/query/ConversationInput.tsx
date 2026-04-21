"use client";
import { useRef, useEffect, useCallback, useState } from "react";
import { Send, RotateCcw, Paperclip, X, Reply, Star, ChevronRight, Hash, FileText, Database, Zap } from "lucide-react";
import { useFavorites } from "@/app/favorites/useFavorites";
import { Strategy, SourceSection } from "./types";

const strategies: { value: Strategy; label: string; title: string }[] = [
    { value: "parallel",       label: "并行",   title: "全文 + 向量 RRF 融合" },
    { value: "sequential",     label: "串行",   title: "全文优先，精确查询" },
    { value: "graph_augmented",label: "图谱",   title: "向量召回 + 图谱扩展" },
    { value: "multi_hop",      label: "多跳",   title: "多跳推理，复杂因果" },
    { value: "counterfactual", label: "反事实", title: "假设推理：去掉 X 后还能满足 Y 吗？" },
];

interface Suggestion {
    type: "entity";
    label: string;
    id: string;
    entity_type: string;
    relationships?: string[];
}

interface Props {
    value: string;
    strategy: Strategy;
    useHyde: boolean;
    loading: boolean;
    streaming: boolean;
    historyLen: number;
    pendingImages: string[];
    quoteSource?: SourceSection | null;
    onChange: (v: string) => void;
    onStrategy: (s: Strategy) => void;
    onHydeToggle: (v: boolean) => void;
    onSubmit: () => void;
    onClear: () => void;
    onAddImages: (imgs: string[]) => void;
    onRemoveImage: (idx: number) => void;
    onClearQuote?: () => void;
}

export default function ConversationInput({
    value, strategy, useHyde, loading, streaming, historyLen, pendingImages,
    quoteSource, onChange, onStrategy, onHydeToggle, onSubmit, onClear,
    onAddImages, onRemoveImage, onClearQuote,
}: Props) {
    const { getFavoriteId, addFavorite, removeFavorite } = useFavorites();
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);
    const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
    const [showSuggestions, setShowSuggestions] = useState(false);
    const [selectedIndex, setSelectedIndex] = useState(0);

    useEffect(() => { textareaRef.current?.focus(); }, []);

    // 联想搜索逻辑
    useEffect(() => {
        const query = value.trim();
        if (query.length < 2) {
            setSuggestions([]);
            setShowSuggestions(false);
            return;
        }

        const timer = setTimeout(async () => {
            try {
                const res = await fetch(`/api/search/autocomplete?q=${encodeURIComponent(query)}`);
                const data = await res.json();
                setSuggestions(data.suggestions || []);
                setShowSuggestions((data.suggestions || []).length > 0);
                setSelectedIndex(0);
            } catch (err) {
                console.error("Autocomplete failed:", err);
            }
        }, 300);

        return () => clearTimeout(timer);
    }, [value]);

    function handleSelectSuggestion(s: Suggestion, rel?: string) {
        let newValue = s.label;
        if (rel) {
            newValue = `${s.label} 的 ${rel}`;
        }
        onChange(newValue);
        setShowSuggestions(false);
        textareaRef.current?.focus();
    }

    // 有引用时自动聚焦输入框
    useEffect(() => {
        if (quoteSource) textareaRef.current?.focus();
    }, [quoteSource]);

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
        <div className="border-t border-gray-800 bg-gray-950 px-4 py-4 relative">
            {/* 联想搜索下拉框 */}
            {showSuggestions && (
                <div className="absolute bottom-full left-4 right-4 mb-2 bg-gray-900 border border-gray-700
                                rounded-xl shadow-2xl overflow-hidden z-50 max-h-80 overflow-y-auto">
                    {suggestions.map((s, idx) => (
                        <div key={idx} className={`border-b border-gray-800 last:border-0`}>
                            <div
                                onClick={() => handleSelectSuggestion(s)}
                                className={`flex items-center gap-3 px-4 py-3 cursor-pointer transition-colors
                                          ${selectedIndex === idx ? "bg-indigo-900/40" : "hover:bg-gray-800"}`}
                            >
                                <div className="w-6 h-6 rounded bg-gray-800 flex items-center justify-center shrink-0">
                                    {s.entity_type === "Section" ? <Hash size={14} className="text-indigo-400" /> :
                                     s.entity_type === "Document" ? <FileText size={14} className="text-amber-400" /> :
                                     <Database size={14} className="text-emerald-400" />}
                                </div>
                                <div className="flex-1 min-w-0">
                                    <div className="text-sm text-gray-200 font-medium truncate">{s.label}</div>
                                    <div className="text-[10px] text-gray-500 uppercase tracking-wider">{s.entity_type}</div>
                                </div>
                                <ChevronRight size={14} className="text-gray-600" />
                            </div>
                            
                            {/* 关系路径联想 (Relationship-aware) */}
                            {s.relationships && s.relationships.length > 0 && (
                                <div className="px-4 pb-3 flex flex-wrap gap-1.5 ml-9">
                                    {s.relationships.slice(0, 5).map(rel => (
                                        <button
                                            key={rel}
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                handleSelectSuggestion(s, rel);
                                            }}
                                            className="px-2 py-0.5 bg-indigo-950/40 border border-indigo-800/50 
                                                       rounded text-[10px] text-indigo-300 hover:bg-indigo-800 
                                                       hover:text-white transition-colors"
                                        >
                                            {rel}
                                        </button>
                                    ))}
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            )}

            {/* 策略 + HyDE 开关 + 清空 */}
            <div className="flex items-center gap-2 mb-3">
                <div className="flex gap-1 bg-gray-900 border border-gray-800 rounded-lg p-0.5">
                    {strategies.map(s => (
                        <button key={s.value} onClick={() => onStrategy(s.value)} title={s.title}
                            className={`px-2.5 py-1 rounded text-xs transition-colors ${strategy === s.value
                                    ? s.value === "counterfactual"
                                        ? "bg-amber-600 text-white"
                                        : "bg-indigo-600 text-white"
                                    : "text-gray-500 hover:text-gray-300"
                                }`}>
                            {s.label}
                        </button>
                    ))}
                </div>

                {/* HyDE 增强模式开关 */}
                <button
                    onClick={() => onHydeToggle(!useHyde)}
                    title="启用后系统先生成假设答案再检索，适合复杂技术问题，响应稍慢"
                    className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg border text-xs transition-colors ${
                        useHyde
                            ? "bg-violet-600 border-violet-500 text-white"
                            : "bg-gray-900 border-gray-800 text-gray-500 hover:text-gray-300"
                    }`}
                >
                    <Zap size={11} className={useHyde ? "text-violet-200" : ""} />
                    增强
                </button>

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

            {/* 引用来源 chip */}
            {quoteSource && (
                <div className="mb-2 px-3 py-2 bg-indigo-950/60 border border-indigo-700/50
                                rounded-xl flex items-start gap-2.5">
                    <Reply size={13} className="text-indigo-400 shrink-0 mt-0.5" />
                    <div className="flex-1 min-w-0">
                        <div className="text-xs text-indigo-300 font-medium leading-snug">
                            追问引用 · <span className="font-mono">{quoteSource.doc_id} §{quoteSource.number}</span>
                        </div>
                        <div className="text-xs text-indigo-400/70 truncate mt-0.5">
                            {quoteSource.title}
                        </div>
                    </div>
                    <button
                        onClick={onClearQuote}
                        className="text-indigo-600 hover:text-indigo-300 transition-colors shrink-0 mt-0.5"
                        title="取消引用"
                    >
                        <X size={12} />
                    </button>
                </div>
            )}

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
                {value.trim() && !streaming && (
                    <button
                        onClick={async () => {
                            const trimmed = value.trim();
                            const favId = getFavoriteId({ type: "query", query_text: trimmed });
                            if (favId) await removeFavorite(favId);
                            else await addFavorite({ type: "query", query_text: trimmed, title: trimmed.slice(0, 80) });
                        }}
                        title={getFavoriteId({ type: "query", query_text: value.trim() }) ? "取消收藏此问题" : "收藏此问题"}
                        className="w-7 h-7 rounded-lg flex items-center justify-center
                         hover:bg-gray-800 transition-colors flex-shrink-0"
                    >
                        <Star
                            size={13}
                            className={getFavoriteId({ type: "query", query_text: value.trim() })
                                ? "text-amber-400 fill-amber-400"
                                : "text-gray-600 hover:text-amber-400"}
                        />
                    </button>
                )}
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
