"use client";

import { X } from "lucide-react";
import { TEvent } from "./types";

interface Props {
    bases:       string[];
    vers:        string[];
    events:      TEvent[];
    displayStep: number;
    selected:    TEvent | null;
    setSelected: (ev: TEvent | null) => void;
}

export function TimelineSidebar({ bases, vers, events, displayStep, selected, setSelected }: Props) {
    return (
        <div className="w-52 border-l border-gray-800 flex flex-col shrink-0 bg-gray-900/20">

            {/* Legend */}
            <div className="p-4 border-b border-gray-800 shrink-0">
                <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">图例</div>
                {(
                    [
                        { color: "#6366f1", label: "初始版本" },
                        { color: "#22c55e", label: "章节净增加" },
                        { color: "#ef4444", label: "章节净减少" },
                        { color: "#3b82f6", label: "内容变更" },
                        { color: "#f59e0b", label: "混合变更" },
                    ] as const
                ).map(({ color, label }) => (
                    <div key={label} className="flex items-center gap-2 mb-1.5">
                        <div className="w-3 h-3 rounded-full shrink-0" style={{ background: color }} />
                        <span className="text-xs text-gray-400">{label}</span>
                    </div>
                ))}
                <div className="mt-3 space-y-0.5 text-xs text-gray-600">
                    <div>气泡大小 = 变更总量</div>
                    <div>虚线箭头 = 版本继承</div>
                    <div>淡色轮廓 = 未来版本</div>
                </div>
            </div>

            {/* Stats */}
            <div className="px-4 py-3 border-b border-gray-800 shrink-0">
                <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">统计</div>
                <div className="space-y-1">
                    {[
                        { label: "文档家族", value: bases.length },
                        { label: "版本跨度", value: vers.length },
                        { label: "事件总数", value: events.length },
                    ].map(({ label, value }) => (
                        <div key={label} className="flex justify-between text-xs">
                            <span className="text-gray-500">{label}</span>
                            <span className="text-white">{value}</span>
                        </div>
                    ))}
                    <div className="flex justify-between text-xs">
                        <span className="text-gray-500">已播放</span>
                        <span className="text-indigo-300">{displayStep} / {events.length}</span>
                    </div>
                </div>
            </div>

            {/* Selected detail */}
            {selected ? (
                <div className="flex-1 overflow-auto p-4">
                    <div className="flex items-center justify-between mb-3">
                        <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">版本详情</span>
                        <button onClick={() => setSelected(null)} className="text-gray-600 hover:text-white transition-colors">
                            <X size={13} />
                        </button>
                    </div>
                    <div className="space-y-3">
                        <div>
                            <div className="text-xs text-gray-600 mb-0.5">文档 ID</div>
                            <div className="text-sm text-white font-mono">{selected.doc_id}</div>
                        </div>
                        <div>
                            <div className="text-xs text-gray-600 mb-0.5">标题</div>
                            <div className="text-xs text-gray-300 leading-snug">{selected.title || "—"}</div>
                        </div>
                        <div className="flex gap-4">
                            <div>
                                <div className="text-xs text-gray-600 mb-0.5">版本</div>
                                <div className="text-xs text-white font-mono">{selected.ver || "初版"}</div>
                            </div>
                            {selected.issue_date && (
                                <div>
                                    <div className="text-xs text-gray-600 mb-0.5">日期</div>
                                    <div className="text-xs text-gray-300">{selected.issue_date}</div>
                                </div>
                            )}
                        </div>
                        <div className="border-t border-gray-800 pt-2">
                            <div className="text-xs text-gray-600 mb-1.5">章节变更统计</div>
                            <div className="space-y-1.5">
                                {[
                                    { color: "bg-green-500", label: "新增",  value: selected.added },
                                    { color: "bg-red-500",   label: "删除",  value: selected.removed },
                                    { color: "bg-blue-500",  label: "变更",  value: selected.changed },
                                ].map(({ color, label, value }) => (
                                    <div key={label} className="flex items-center justify-between text-xs">
                                        <span className="flex items-center gap-1.5">
                                            <span className={`w-2 h-2 rounded-full ${color} inline-block`} />
                                            {label}
                                        </span>
                                        <span className="text-white font-medium">{value}</span>
                                    </div>
                                ))}
                                <div className="flex items-center justify-between text-xs border-t border-gray-800 pt-1 mt-1">
                                    <span className="text-gray-500">合计</span>
                                    <span className="text-white font-semibold">{selected.total}</span>
                                </div>
                            </div>
                        </div>
                        {selected.supersedes.length > 0 && (
                            <div className="border-t border-gray-800 pt-2">
                                <div className="text-xs text-gray-600 mb-1">继承自</div>
                                {selected.supersedes.map(id => (
                                    <div key={id} className="text-xs text-indigo-400 font-mono">{id}</div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>
            ) : (
                <div className="flex-1 flex items-center justify-center p-4">
                    <p className="text-xs text-gray-700 text-center leading-relaxed">
                        点击气泡<br />查看版本详情
                    </p>
                </div>
            )}
        </div>
    );
}
