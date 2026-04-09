"use client";

import { useState, useEffect } from "react";
import { UserRow, getToken } from "./types";

interface Props {
    showMsg:   (m: string) => void;
    showError: (e: string) => void;
}

export function AdminTab({ showMsg, showError }: Props) {
    const [users, setUsers]           = useState<UserRow[]>([]);
    const [showCreate, setShowCreate] = useState(false);
    const [createForm, setCreateForm] = useState({
        username: "", password: "", full_name: "", department: "", email: "", is_admin: false,
    });
    const [creating, setCreating]         = useState(false);
    const [resetTarget, setResetTarget]   = useState<UserRow | null>(null);
    const [resetPw, setResetPw]           = useState("");
    const [resetting, setResetting]       = useState(false);

    useEffect(() => { loadUsers(); }, []);

    async function loadUsers() {
        const res = await fetch("/api/users", { headers: { Authorization: `Bearer ${getToken()}` } });
        if (res.ok) setUsers(await res.json());
    }

    async function toggleUser(userId: string) {
        const res = await fetch(`/api/users/${userId}/toggle`, {
            method: "PUT", headers: { Authorization: `Bearer ${getToken()}` },
        });
        if (res.ok) { loadUsers(); showMsg("操作成功"); }
        else showError("操作失败");
    }

    async function toggleAdmin(userId: string) {
        const res = await fetch(`/api/users/${userId}/admin`, {
            method: "PUT", headers: { Authorization: `Bearer ${getToken()}` },
        });
        if (res.ok) { loadUsers(); showMsg("操作成功"); }
        else showError("操作失败");
    }

    async function createUser() {
        if (!createForm.username || !createForm.password) { showError("工号和密码为必填项"); return; }
        setCreating(true);
        try {
            const res = await fetch("/api/users", {
                method: "POST",
                headers: { "Content-Type": "application/json", Authorization: `Bearer ${getToken()}` },
                body: JSON.stringify(createForm),
            });
            const data = await res.json();
            if (!res.ok) { showError(data.detail || "创建失败"); return; }
            showMsg(`用户 ${data.username} 创建成功`);
            setShowCreate(false);
            setCreateForm({ username: "", password: "", full_name: "", department: "", email: "", is_admin: false });
            await loadUsers();
        } finally {
            setCreating(false);
        }
    }

    async function doResetPassword() {
        if (!resetTarget || !resetPw.trim()) return;
        if (resetPw.length < 6) { showError("密码至少6位"); return; }
        setResetting(true);
        try {
            const res = await fetch(`/api/users/${resetTarget.user_id}/reset-password`, {
                method: "POST",
                headers: { "Content-Type": "application/json", Authorization: `Bearer ${getToken()}` },
                body: JSON.stringify({ new_password: resetPw }),
            });
            if (res.ok) {
                showMsg(`已重置 ${resetTarget.username} 的密码`);
                setResetTarget(null); setResetPw("");
            } else {
                const err = await res.json();
                showError(err.detail || "重置失败");
            }
        } finally {
            setResetting(false);
        }
    }

    return (
        <div className="space-y-4">
            {/* 操作栏 */}
            <div className="flex items-center justify-between">
                <span className="text-sm text-gray-500">共 {users.length} 个用户</span>
                <button
                    onClick={() => { setShowCreate(v => !v); setCreateForm({ username: "", password: "", full_name: "", department: "", email: "", is_admin: false }); }}
                    className="px-4 py-1.5 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-500 transition-colors"
                >
                    + 新建用户
                </button>
            </div>

            {/* 新建用户面板 */}
            {showCreate && (
                <div className="bg-gray-900 border border-indigo-700/50 rounded-xl p-5 space-y-4">
                    <h3 className="text-sm font-semibold text-white">新建用户</h3>
                    <div className="grid grid-cols-2 gap-3">
                        <div>
                            <label className="text-xs text-gray-500 mb-1 block">工号 <span className="text-red-400">*</span></label>
                            <input value={createForm.username}
                                onChange={e => setCreateForm(f => ({ ...f, username: e.target.value }))}
                                placeholder="6位数字工号" maxLength={6}
                                className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded text-sm text-gray-200 outline-none focus:border-indigo-500" />
                        </div>
                        <div>
                            <label className="text-xs text-gray-500 mb-1 block">初始密码 <span className="text-red-400">*</span></label>
                            <input type="password" value={createForm.password}
                                onChange={e => setCreateForm(f => ({ ...f, password: e.target.value }))}
                                placeholder="至少6位"
                                className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded text-sm text-gray-200 outline-none focus:border-indigo-500" />
                        </div>
                        <div>
                            <label className="text-xs text-gray-500 mb-1 block">姓名</label>
                            <input value={createForm.full_name}
                                onChange={e => setCreateForm(f => ({ ...f, full_name: e.target.value }))}
                                placeholder="真实姓名"
                                className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded text-sm text-gray-200 outline-none focus:border-indigo-500" />
                        </div>
                        <div>
                            <label className="text-xs text-gray-500 mb-1 block">部门</label>
                            <input value={createForm.department}
                                onChange={e => setCreateForm(f => ({ ...f, department: e.target.value }))}
                                placeholder="所在部门"
                                className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded text-sm text-gray-200 outline-none focus:border-indigo-500" />
                        </div>
                        <div className="col-span-2">
                            <label className="text-xs text-gray-500 mb-1 block">邮箱</label>
                            <input type="email" value={createForm.email}
                                onChange={e => setCreateForm(f => ({ ...f, email: e.target.value }))}
                                placeholder="工作邮箱（选填）"
                                className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded text-sm text-gray-200 outline-none focus:border-indigo-500" />
                        </div>
                    </div>
                    <div className="pt-1">
                        <label className="text-xs text-gray-500 mb-2 block">用户权限</label>
                        <div className="flex gap-3">
                            {[
                                { value: false, label: "普通用户", desc: "可查询、浏览文档" },
                                { value: true,  label: "管理员",   desc: "全部权限 + 用户管理" },
                            ].map(opt => (
                                <label key={String(opt.value)}
                                    className={`flex items-start gap-2.5 flex-1 p-3 rounded-lg border cursor-pointer transition-colors ${
                                        createForm.is_admin === opt.value
                                            ? "border-indigo-600 bg-indigo-600/10"
                                            : "border-gray-700 hover:border-gray-600"
                                    }`}>
                                    <input type="radio" name="is_admin"
                                        checked={createForm.is_admin === opt.value}
                                        onChange={() => setCreateForm(f => ({ ...f, is_admin: opt.value }))}
                                        className="mt-0.5 accent-indigo-600" />
                                    <div>
                                        <div className="text-sm text-gray-200">{opt.label}</div>
                                        <div className="text-xs text-gray-500 mt-0.5">{opt.desc}</div>
                                    </div>
                                </label>
                            ))}
                        </div>
                    </div>
                    <div className="flex gap-2 pt-1">
                        <button onClick={createUser} disabled={creating}
                            className="px-5 py-2 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-500 disabled:opacity-40">
                            {creating ? "创建中..." : "创建用户"}
                        </button>
                        <button onClick={() => setShowCreate(false)}
                            className="px-4 py-2 bg-gray-800 text-gray-400 text-sm rounded-lg hover:text-white">
                            取消
                        </button>
                    </div>
                </div>
            )}

            {/* 重置密码弹窗 */}
            {resetTarget && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
                    <div className="bg-gray-900 border border-gray-700 rounded-2xl p-6 w-80 shadow-2xl">
                        <h3 className="text-sm font-semibold text-white mb-1">重置密码</h3>
                        <p className="text-xs text-gray-500 mb-4">
                            为用户 <span className="text-indigo-400 font-mono">{resetTarget.username}</span>
                            {resetTarget.full_name ? `（${resetTarget.full_name}）` : ""} 设置新密码
                        </p>
                        <input type="password" value={resetPw}
                            onChange={e => setResetPw(e.target.value)}
                            placeholder="新密码（至少6位）"
                            className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded text-sm text-gray-200 outline-none focus:border-indigo-500 mb-4"
                            onKeyDown={e => e.key === "Enter" && doResetPassword()}
                            autoFocus />
                        <div className="flex gap-2">
                            <button onClick={doResetPassword} disabled={resetting || !resetPw.trim()}
                                className="flex-1 py-2 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-500 disabled:opacity-40 transition-colors">
                                {resetting ? "重置中..." : "确认重置"}
                            </button>
                            <button onClick={() => { setResetTarget(null); setResetPw(""); }}
                                className="px-4 py-2 bg-gray-800 text-gray-400 text-sm rounded-lg hover:text-white">
                                取消
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* 用户列表 */}
            <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
                <table className="w-full text-sm">
                    <thead>
                        <tr className="border-b border-gray-800 text-gray-400 text-left">
                            <th className="px-4 py-3">工号</th>
                            <th className="px-4 py-3">姓名</th>
                            <th className="px-4 py-3">部门</th>
                            <th className="px-4 py-3">权限</th>
                            <th className="px-4 py-3">状态</th>
                            <th className="px-4 py-3">操作</th>
                        </tr>
                    </thead>
                    <tbody>
                        {users.map(u => (
                            <tr key={u.user_id} className="border-b border-gray-800/50 hover:bg-gray-800/20">
                                <td className="px-4 py-3 font-mono text-gray-300">{u.username}</td>
                                <td className="px-4 py-3 text-gray-300">{u.full_name || "—"}</td>
                                <td className="px-4 py-3 text-gray-400">{u.department || "—"}</td>
                                <td className="px-4 py-3">
                                    <span className={`px-2 py-0.5 rounded text-xs ${u.is_admin ? "bg-indigo-500/20 text-indigo-400" : "bg-gray-700 text-gray-400"}`}>
                                        {u.is_admin ? "管理员" : "普通用户"}
                                    </span>
                                </td>
                                <td className="px-4 py-3">
                                    <span className={`px-2 py-0.5 rounded text-xs ${u.is_active ? "bg-green-500/20 text-green-400" : "bg-red-500/20 text-red-400"}`}>
                                        {u.is_active ? "启用" : "禁用"}
                                    </span>
                                </td>
                                <td className="px-4 py-3">
                                    <div className="flex gap-1.5">
                                        <button onClick={() => toggleUser(u.user_id)}
                                            className="px-2 py-1 bg-gray-800 text-gray-400 text-xs rounded hover:text-white transition-colors">
                                            {u.is_active ? "禁用" : "启用"}
                                        </button>
                                        <button onClick={() => toggleAdmin(u.user_id)}
                                            className="px-2 py-1 bg-gray-800 text-gray-400 text-xs rounded hover:text-white transition-colors">
                                            {u.is_admin ? "撤销管理员" : "设管理员"}
                                        </button>
                                        <button onClick={() => { setResetTarget(u); setResetPw(""); }}
                                            className="px-2 py-1 bg-gray-800 text-amber-500/70 text-xs rounded hover:text-amber-400 transition-colors">
                                            重置密码
                                        </button>
                                    </div>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
