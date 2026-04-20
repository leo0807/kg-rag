"use client";

import { X, RefreshCw, Ruler, AlertCircle } from "lucide-react";

interface Annotation {
    type:      string;
    raw:       string;
    parameter: string;
    value:     string;
    value_max: string;
    value_min: string;
    unit:      string;
}

interface DrawingImage {
    image_id:          string;
    caption:           string;
    path:              string;
    url:               string | null;
    description:       string;
    is_drawing:        boolean;
    part_numbers:      string[];
    annotations:       Annotation[];
    assembly_relations:string[];
    drawing_summary:   string;
    section_number:    string;
    section_title:     string;
}

interface Props {
    image:       DrawingImage;
    onClose:     () => void;
    onReanalyze: (imageId: string) => void;
    reanalyzing: boolean;
}

const TYPE_LABEL: Record<string, string> = {
    tolerance:  "公差",
    dimension:  "尺寸",
    surface:    "表面粗糙度",
    other:      "其他",
};

const TYPE_COLOR: Record<string, string> = {
    tolerance: "bg-amber-900/40 text-amber-300 border-amber-700/40",
    dimension: "bg-blue-900/40 text-blue-300 border-blue-700/40",
    surface:   "bg-emerald-900/40 text-emerald-300 border-emerald-700/40",
    other:     "bg-gray-800 text-gray-400 border-gray-700",
};

export function DrawingViewer({ image, onClose, onReanalyze, reanalyzing }: Props) {
    const imgSrc = image.url ?? null;

    return (
        <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4"
            onClick={onClose}
        >
            <div
                className="bg-gray-950 border border-gray-800 rounded-2xl w-full max-w-4xl max-h-[90vh]
                           overflow-hidden flex flex-col shadow-2xl"
                onClick={e => e.stopPropagation()}
            >
                {/* 头部 */}
                <div className="flex items-center justify-between px-5 py-3.5 border-b border-gray-800 shrink-0">
                    <div className="min-w-0">
                        <div className="flex items-center gap-2">
                            <Ruler size={14} className="text-indigo-400 shrink-0" />
                            <span className="text-sm font-medium text-white truncate">
                                {image.caption || image.drawing_summary || "工程图纸"}
                            </span>
                            {image.is_drawing && (
                                <span className="px-1.5 py-0.5 bg-indigo-900/50 text-indigo-300 border border-indigo-700/40
                                                 rounded text-xs font-medium shrink-0">
                                    工程图纸
                                </span>
                            )}
                        </div>
                        <div className="text-xs text-gray-500 mt-0.5 truncate">
                            §{image.section_number} {image.section_title}
                        </div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0 ml-3">
                        <button
                            onClick={() => onReanalyze(image.image_id)}
                            disabled={reanalyzing}
                            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs
                                       text-gray-400 hover:text-white bg-gray-800 hover:bg-gray-700
                                       border border-gray-700 transition-colors disabled:opacity-50"
                            title="重新进行图纸分析"
                        >
                            <RefreshCw size={11} className={reanalyzing ? "animate-spin" : ""} />
                            重新分析
                        </button>
                        <button
                            onClick={onClose}
                            className="p-1.5 rounded-lg text-gray-500 hover:text-white hover:bg-gray-800 transition-colors"
                        >
                            <X size={16} />
                        </button>
                    </div>
                </div>

                {/* 主体：图片 + 标注侧栏 */}
                <div className="flex flex-1 overflow-hidden">
                    {/* 图片区 */}
                    <div className="flex-1 overflow-auto bg-gray-900 flex items-center justify-center p-4">
                        {imgSrc ? (
                            <img
                                src={imgSrc as string}
                                alt={image.caption || "工程图纸"}
                                className="max-w-full max-h-full object-contain rounded"
                                onError={e => {
                                    const el = e.currentTarget;
                                    el.style.display = "none";
                                    const fb = el.nextSibling as HTMLElement | null;
                                    if (fb) fb.removeAttribute("hidden");
                                }}
                            />
                        ) : null}
                        <span hidden={!!imgSrc} className="text-sm text-gray-500">图片暂不可用</span>
                    </div>

                    {/* 标注侧栏 */}
                    <div className="w-72 shrink-0 border-l border-gray-800 overflow-y-auto">
                        {/* 零件编号 */}
                        {image.part_numbers.length > 0 && (
                            <div className="px-4 py-3 border-b border-gray-800">
                                <div className="text-xs text-gray-500 uppercase tracking-wider mb-2">零件编号</div>
                                <div className="flex flex-wrap gap-1.5">
                                    {image.part_numbers.map((pn, i) => (
                                        <span key={i} className="px-2 py-0.5 bg-gray-800 border border-gray-700
                                                                  rounded text-xs font-mono text-gray-300">
                                            {pn}
                                        </span>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* 尺寸与公差标注 */}
                        {image.annotations.length > 0 ? (
                            <div className="px-4 py-3 border-b border-gray-800">
                                <div className="text-xs text-gray-500 uppercase tracking-wider mb-2">
                                    尺寸 & 公差标注 · {image.annotations.length} 条
                                </div>
                                <div className="space-y-2">
                                    {image.annotations.map((ann, i) => (
                                        <div key={i} className={`px-3 py-2 rounded-lg border text-xs ${TYPE_COLOR[ann.type] ?? TYPE_COLOR.other}`}>
                                            <div className="flex items-center justify-between gap-2 mb-0.5">
                                                <span className="font-medium truncate">{ann.parameter || ann.raw}</span>
                                                <span className="text-xs opacity-70 shrink-0">{TYPE_LABEL[ann.type] ?? ann.type}</span>
                                            </div>
                                            <div className="font-mono text-sm">
                                                {ann.raw}
                                                {ann.unit && <span className="ml-1 opacity-60">{ann.unit}</span>}
                                            </div>
                                            {(ann.value_min || ann.value_max) && (
                                                <div className="mt-0.5 opacity-70">
                                                    {ann.value_min && `≥ ${ann.value_min}`}
                                                    {ann.value_min && ann.value_max && " ~ "}
                                                    {ann.value_max && `≤ ${ann.value_max}`}
                                                    {ann.unit && ` ${ann.unit}`}
                                                </div>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            </div>
                        ) : (
                            <div className="px-4 py-4 border-b border-gray-800 flex items-center gap-2 text-xs text-gray-600">
                                <AlertCircle size={13} />
                                暂无尺寸标注，点击"重新分析"提取
                            </div>
                        )}

                        {/* 装配关系 */}
                        {image.assembly_relations.length > 0 && (
                            <div className="px-4 py-3">
                                <div className="text-xs text-gray-500 uppercase tracking-wider mb-2">装配关系</div>
                                <ul className="space-y-1.5">
                                    {image.assembly_relations.map((rel, i) => (
                                        <li key={i} className="text-xs text-gray-400 flex items-start gap-1.5">
                                            <span className="text-gray-600 mt-0.5 shrink-0">•</span>
                                            {rel}
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        )}

                        {/* 图纸总结 */}
                        {image.drawing_summary && (
                            <div className="px-4 py-3 border-t border-gray-800">
                                <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">AI 摘要</div>
                                <p className="text-xs text-gray-400 leading-relaxed">{image.drawing_summary}</p>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
