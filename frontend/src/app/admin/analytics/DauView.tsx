"use client";

import { DauPoint } from "./types";
import { DauChart } from "./components";

interface Props {
    dau:  DauPoint[];
    maxQ: number;
}

export function DauView({ dau, maxQ }: Props) {
    return (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
            <div className="flex items-center justify-between mb-4">
                <div className="text-sm font-medium text-gray-300">每日活跃用户 & 查询量</div>
                <div className="flex items-center gap-4 text-xs text-gray-500">
                    <span className="flex items-center gap-1.5">
                        <span className="w-3 h-3 rounded-sm bg-indigo-600 inline-block" />查询数
                    </span>
                    <span className="flex items-center gap-1.5">
                        <span className="w-3 h-3 rounded-sm bg-emerald-700 inline-block" />活跃用户
                    </span>
                </div>
            </div>
            <DauChart data={dau} maxQ={maxQ} />
            <div className="mt-4 overflow-x-auto">
                <table className="w-full text-xs">
                    <thead>
                        <tr className="text-gray-500">
                            <th className="text-left px-2 py-1">日期</th>
                            <th className="text-right px-2 py-1">活跃用户</th>
                            <th className="text-right px-2 py-1">查询次数</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-800">
                        {[...dau].reverse().map(d => (
                            <tr key={d.date} className="hover:bg-gray-800/50">
                                <td className="px-2 py-1.5 font-mono text-gray-400">{d.date}</td>
                                <td className="px-2 py-1.5 text-right text-gray-300">{d.active_users}</td>
                                <td className="px-2 py-1.5 text-right text-white font-medium">{d.queries}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
                {dau.length === 0 && (
                    <div className="text-center py-8 text-gray-600">暂无数据</div>
                )}
            </div>
        </div>
    );
}
