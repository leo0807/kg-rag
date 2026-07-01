"use client";

import type { UserRow } from "./types";

interface Props {
  target:    UserRow;
  password:  string;
  resetting: boolean;
  onChange:  (pw: string) => void;
  onConfirm: () => void;
  onCancel:  () => void;
}

export function ResetPasswordModal({ target, password, resetting, onChange, onConfirm, onCancel }: Props) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4">
      <div className="w-full max-w-sm rounded-2xl border border-gray-700 bg-gray-900 p-6 shadow-2xl">
        <h3 className="text-sm font-semibold text-white mb-1">重置密码</h3>
        <p className="text-xs text-gray-500 mb-4">
          为用户 <span className="text-indigo-400 font-mono">{target.username}</span>
          {target.full_name ? `（${target.full_name}）` : ""} 设置新密码
        </p>
        <input
          type="password" value={password} onChange={e => onChange(e.target.value)}
          placeholder="新密码（至少6位）" onKeyDown={e => e.key === "Enter" && onConfirm()}
          className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded text-sm text-gray-200 outline-none focus:border-indigo-500 mb-4"
        />
        <div className="flex gap-2">
          <button type="button" onClick={onConfirm} disabled={resetting || !password.trim()}
            className="flex-1 py-2 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-500 disabled:opacity-40 transition-colors">
            {resetting ? "重置中..." : "确认重置"}
          </button>
          <button type="button" onClick={onCancel}
            className="px-4 py-2 bg-gray-800 text-gray-400 text-sm rounded-lg hover:text-white">
            取消
          </button>
        </div>
      </div>
    </div>
  );
}
