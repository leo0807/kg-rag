"use client";

import { DeptRow } from "./types";
import { StrategyBadge } from "./components";

interface Props {
    rows:    DeptRow[];
    sortKey: string;
    sortAsc: boolean;
    onSort:  (col: string) => void;
}

function SortTh({ col, label, right, sortKey, sortAsc, onSort }: {
    col: string; label: string; right?: boolean;
    sortKey: string; sortAsc: boolean; onSort: (col: string) => void;
}) {
    return (
        <th
            className={`px-3 py-2.5 text-xs font-medium text-gray-400 cursor-pointer hover:text-white whitespace-nowrap select-none ${right ? "text-right" : "text-left"}`}
            onClick={() => onSort(col)}
        >
            {label}
            {sortKey === col && <span className="ml-1 text-indigo-400">{sortAsc ? "↑" : "↓"}</span>}
        </th>
    );
}

export function DeptTable({ rows, sortKey, sortAsc, onSort }: Props) {
    const th = (col: string, label: string, right?: boolean) => (
        <SortTh col={col} label={label} right={right} sortKey={sortKey} sortAsc={sortAsc} onSort={onSort} />
    );

    return (
        <div className="overflow-x-auto">
            <table className="w-full text-sm">
                <thead className="bg-gray-900 sticky top-0 z-10">
                    <tr>
                        {th("department",            "部门")}
                        {th("user_count",            "活跃人数", true)}
                        {th("avg_active_days",       "人均活跃天", true)}
                        {th("total_queries",         "总查询", true)}
                        {th("weekly_queries",        "周均查询", true)}
                        {th("total_conversations",   "对话数", true)}
                        {th("avg_turns_per_session", "均轮数", true)}
                        {th("top_strategy",          "主用策略")}
                    </tr>
                </thead>
                <tbody className="divide-y divide-gray-800">
                    {rows.map(row => (
                        <tr key={row.department} className="hover:bg-gray-900/50 transition-colors">
                            <td className="px-3 py-2.5 font-medium text-gray-200">{row.department}</td>
                            <td className="px-3 py-2.5 text-right text-gray-300">{row.user_count}</td>
                            <td className="px-3 py-2.5 text-right text-gray-400">{row.avg_active_days}</td>
                            <td className="px-3 py-2.5 text-right font-semibold text-white">{row.total_queries.toLocaleString()}</td>
                            <td className="px-3 py-2.5 text-right text-gray-400">{row.weekly_queries}</td>
                            <td className="px-3 py-2.5 text-right text-gray-300">{row.total_conversations}</td>
                            <td className="px-3 py-2.5 text-right text-gray-400">{row.avg_turns_per_session ?? "—"}</td>
                            <td className="px-3 py-2.5"><StrategyBadge strategy={row.top_strategy} /></td>
                        </tr>
                    ))}
                </tbody>
            </table>
            {rows.length === 0 && (
                <div className="text-center py-12 text-gray-600 text-sm">暂无部门数据</div>
            )}
        </div>
    );
}
