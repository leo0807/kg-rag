"use client";

import { useState, useEffect } from "react";
import { UserInfo, getToken } from "./types";

interface Props {
    showMsg:   (m: string) => void;
    showError: (e: string) => void;
}

export function ProfileTab({ showMsg, showError }: Props) {
    const [profile, setProfile] = useState<UserInfo | null>(null);

    useEffect(() => {
        fetch("/api/auth/profile", { headers: { Authorization: `Bearer ${getToken()}` } })
            .then(r => r.ok ? r.json() : null)
            .then(data => data && setProfile(data));
    }, []);

    async function save() {
        if (!profile) return;
        const res = await fetch("/api/auth/profile", {
            method: "PUT",
            headers: { "Content-Type": "application/json", Authorization: `Bearer ${getToken()}` },
            body: JSON.stringify(profile),
        });
        if (res.ok) {
            const data = await res.json();
            const stored = JSON.parse(localStorage.getItem("user") ?? "{}");
            localStorage.setItem("user", JSON.stringify({ ...stored, ...data }));
            showMsg("个人资料已保存");
        } else {
            const err = await res.json();
            showError(err.detail || "保存失败");
        }
    }

    if (!profile) return <div className="text-sm text-gray-500">加载中…</div>;

    return (
        <div className="space-y-4 bg-gray-900 rounded-xl p-5 border border-gray-800">
            <div className="grid grid-cols-2 gap-4">
                <div>
                    <label className="text-xs text-gray-500 mb-1 block">工号</label>
                    <input value={profile.username} disabled
                        className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded text-sm text-gray-500 cursor-not-allowed" />
                </div>
                <div>
                    <label className="text-xs text-gray-500 mb-1 block">姓名</label>
                    <input value={profile.full_name}
                        onChange={e => setProfile(p => p ? { ...p, full_name: e.target.value } : p)}
                        className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded text-sm text-gray-200 outline-none focus:border-indigo-500" />
                </div>
            </div>
            <div>
                <label className="text-xs text-gray-500 mb-1 block">部门</label>
                <input value={profile.department}
                    onChange={e => setProfile(p => p ? { ...p, department: e.target.value } : p)}
                    className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded text-sm text-gray-200 outline-none focus:border-indigo-500" />
            </div>
            <div>
                <label className="text-xs text-gray-500 mb-1 block">邮箱</label>
                <input type="email" value={profile.email}
                    onChange={e => setProfile(p => p ? { ...p, email: e.target.value } : p)}
                    className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded text-sm text-gray-200 outline-none focus:border-indigo-500" />
            </div>
            <button onClick={save}
                className="px-5 py-2 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-500">
                保存
            </button>
        </div>
    );
}
