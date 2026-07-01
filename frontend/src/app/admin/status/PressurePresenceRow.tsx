"use client";

import { AlertTriangle, Users } from "lucide-react";

type PressureLevel = "low" | "medium" | "high";

function pressureTone(level: PressureLevel) {
  if (level === "high")   return "bg-red-500/15 text-red-300 border-red-500/20";
  if (level === "medium") return "bg-amber-500/15 text-amber-300 border-amber-500/20";
  return "bg-emerald-500/15 text-emerald-300 border-emerald-500/20";
}

interface User { user_id: string; username: string; full_name: string; last_seen: number }

interface Props {
  pressure: { level: PressureLevel; score: number; summary: string; factors: string[] };
  presence: { active_users: number; users: User[] };
}

export function PressurePresenceRow({ pressure, presence }: Props) {
  return (
    <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
      <div className="rounded-2xl border border-gray-800 bg-gray-900 p-6">
        <div className="mb-4 flex items-center gap-2">
          <AlertTriangle size={16} className="text-indigo-400" />
          <h2 className="text-sm font-bold text-gray-200">压力分析</h2>
        </div>
        <div className={`mb-4 rounded-2xl border px-4 py-3 ${pressureTone(pressure.level)}`}>
          <div className="text-sm font-semibold">{pressure.summary}</div>
          <div className="mt-1 text-xs opacity-80">综合评分 {pressure.score} / 100</div>
        </div>
        <div className="space-y-3">
          {(pressure.factors ?? []).map((factor) => (
            <div key={factor} className="rounded-xl bg-gray-950/70 px-3 py-2 text-sm text-gray-300">
              {factor}
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-2xl border border-gray-800 bg-gray-900 p-6">
        <div className="mb-4 flex items-center gap-2">
          <Users size={16} className="text-sky-400" />
          <h2 className="text-sm font-bold text-gray-200">最近在线用户</h2>
        </div>
        <div className="space-y-3">
          {presence.users.length ? (
            presence.users.map((user) => (
              <div key={user.user_id}
                className="flex items-center justify-between rounded-xl bg-gray-950/70 px-3 py-3">
                <div>
                  <div className="text-sm font-medium text-white">{user.full_name || user.username}</div>
                  <div className="text-xs text-gray-500">{user.username}</div>
                </div>
                <div className="text-xs text-gray-500">
                  {new Date(user.last_seen * 1000).toLocaleTimeString()}
                </div>
              </div>
            ))
          ) : (
            <div className="rounded-xl bg-gray-950/70 px-3 py-4 text-sm text-gray-500">
              当前暂无活跃用户
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
