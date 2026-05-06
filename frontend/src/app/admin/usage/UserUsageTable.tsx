"use client";

import { useEffect, useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { fetchApi } from "@/lib/api";

interface UserRow {
  user_id: string;
  username: string;
  department: string;
  today_requests: number;
  today_tokens: number;
  today_cost_usd: number;
  week_requests: number;
  week_tokens: number;
  week_cost_usd: number;
  last_active: string | null;
}

type Period = "today" | "week";
type SortKey = "requests" | "tokens" | "cost";

function fmtK(n: number) {
  return n >= 1000 ? `${(n / 1000).toFixed(1)}K` : String(n);
}

export function UserUsageTable() {
  const [users, setUsers] = useState<UserRow[]>([]);
  const [total, setTotal] = useState(0);
  const [activeToday, setActiveToday] = useState(0);
  const [period, setPeriod] = useState<Period>("today");
  const [sortKey, setSortKey] = useState<SortKey>("requests");
  const [sortAsc, setSortAsc] = useState(false);

  useEffect(() => {
    fetchApi<{ users: UserRow[]; total_users: number; active_today: number }>("/api/admin/usage/users")
      .then((d) => { setUsers(d.users); setTotal(d.total_users); setActiveToday(d.active_today); })
      .catch(() => {});
  }, []);

  function toggleSort(key: SortKey) {
    if (sortKey === key) setSortAsc((v) => !v);
    else { setSortKey(key); setSortAsc(false); }
  }

  const prefix = period === "today" ? "today" : "week";
  const sorted = [...users].sort((a, b) => {
    const av = a[`${prefix}_${sortKey === "cost" ? "cost_usd" : sortKey}` as keyof UserRow] as number;
    const bv = b[`${prefix}_${sortKey === "cost" ? "cost_usd" : sortKey}` as keyof UserRow] as number;
    return sortAsc ? av - bv : bv - av;
  });

  if (users.length === 0) return null;

  function SortIcon({ k }: { k: SortKey }) {
    if (sortKey !== k) return null;
    return sortAsc ? <ChevronUp size={11} className="inline ml-0.5" /> : <ChevronDown size={11} className="inline ml-0.5" />;
  }

  return (
    <div className="rounded-3xl border border-gray-800 bg-gray-900 p-5">
      <div className="flex items-center justify-between mb-4">
        <div>
          <span className="text-white font-medium">用户用量排行</span>
          <span className="ml-2 text-xs text-gray-500">{total} 用户 · 今日活跃 {activeToday}</span>
        </div>
        <div className="flex gap-1">
          {(["today", "week"] as Period[]).map((p) => (
            <button key={p} type="button" onClick={() => setPeriod(p)}
              className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${period === p ? "bg-indigo-600 text-white" : "text-gray-400 hover:text-white bg-gray-800"}`}>
              {p === "today" ? "今日" : "本周"}
            </button>
          ))}
        </div>
      </div>
      <div className="overflow-auto">
        <table className="w-full text-sm">
          <thead className="text-gray-400 text-left text-xs">
            <tr>
              <th className="pb-3 pr-4">用户</th>
              <th className="pb-3 pr-4">部门</th>
              <th className="pb-3 pr-4 cursor-pointer hover:text-gray-200" onClick={() => toggleSort("requests")}>
                请求数<SortIcon k="requests" />
              </th>
              <th className="pb-3 pr-4 cursor-pointer hover:text-gray-200" onClick={() => toggleSort("tokens")}>
                Token<SortIcon k="tokens" />
              </th>
              <th className="pb-3 pr-4 cursor-pointer hover:text-gray-200" onClick={() => toggleSort("cost")}>
                费用<SortIcon k="cost" />
              </th>
              <th className="pb-3 text-right">最后活跃</th>
            </tr>
          </thead>
          <tbody className="text-gray-300">
            {sorted.map((u) => (
              <tr key={u.user_id} className="border-t border-gray-800 hover:bg-gray-800/40">
                <td className="py-2 pr-4 font-medium text-white">{u.username}</td>
                <td className="py-2 pr-4 text-xs text-gray-500">{u.department || "—"}</td>
                <td className="py-2 pr-4">{(period === "today" ? u.today_requests : u.week_requests).toLocaleString()}</td>
                <td className="py-2 pr-4">{fmtK(period === "today" ? u.today_tokens : u.week_tokens)}</td>
                <td className="py-2 pr-4">${(period === "today" ? u.today_cost_usd : u.week_cost_usd).toFixed(3)}</td>
                <td className="py-2 text-right text-xs text-gray-500">{u.last_active ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
