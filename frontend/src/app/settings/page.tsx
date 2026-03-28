"use client";

import { useState, useEffect } from "react";

type Tab = "profile" | "password" | "model" | "admin" | "audit";

interface UserInfo {
    username: string;
    full_name: string;
    department: string;
    email: string;
    is_admin: boolean;
}

interface ModelSettings {
    embedding_mode: string;
    embedding_model: string;
    embedding_api_url: string;
    embedding_api_key: string;
    reranker_mode: string;
    reranker_model: string;
    query_top_k: string;
    query_strategy: string;
}

interface UserRow {
    user_id: string;
    username: string;
    full_name: string;
    department: string;
    is_admin: boolean;
    is_active: boolean;
    created_at: string;
}

interface AuditRow {
    id: number;
    username: string;
    full_name: string;
    action: string;
    resource: string;
    detail: string;
    created_at: string;
}

function getToken() {
    return localStorage.getItem("token") ?? "";
}

export default function SettingsPage() {
    const [tab, setTab] = useState<Tab>("profile");
    const [profile, setProfile] = useState<UserInfo | null>(null);
    const [settings, setSettings] = useState<ModelSettings | null>(null);
    const [users, setUsers] = useState<UserRow[]>([]);
    const [msg, setMsg] = useState("");
    const [error, setError] = useState("");
    const [isAdmin, setIsAdmin] = useState(false);
    const [auditLogs, setAuditLogs] = useState<AuditRow[]>([]);
    const [auditTotal, setAuditTotal] = useState(0);
    const [auditPage, setAuditPage] = useState(1);

    const [pwForm, setPwForm] = useState({
        old_password: "",
        new_password: "",
        confirm: "",
    });

    useEffect(() => {

        const stored = localStorage.getItem("user");
        if (stored) {
            const u = JSON.parse(stored);
            setIsAdmin(u.is_admin ?? false);
            if (u.is_admin) {
                loadUsers();
                loadAuditLogs();
            }
        }
        loadProfile();
        loadSettings();
    }, []);

    async function loadAuditLogs(page = 1) {
        const res = await fetch(`/api/users/audit-logs?page=${page}&per_page=15`, {
            headers: { "Authorization": `Bearer ${getToken()}` },
        });
        const data = await res.json();
        setAuditLogs(data.data);
        setAuditTotal(data.total);
        setAuditPage(page);
    }

    async function loadProfile() {
        const res = await fetch("/api/auth/profile", {
            headers: { "Authorization": `Bearer ${getToken()}` },
        });
        setProfile(await res.json());
    }

    async function loadSettings() {
        const res = await fetch("/api/settings/user", {
            headers: { "Authorization": `Bearer ${getToken()}` },
        });
        setSettings(await res.json());
    }

    async function loadUsers() {
        const res = await fetch("/api/users", {
            headers: { "Authorization": `Bearer ${getToken()}` },
        });
        setUsers(await res.json());
    }

    function showMsg(m: string) {
        setMsg(m); setError("");
        setTimeout(() => setMsg(""), 3000);
    }

    function showError(e: string) {
        setError(e); setMsg("");
        setTimeout(() => setError(""), 3000);
    }

    async function saveProfile() {
        if (!profile) return;
        const res = await fetch("/api/auth/profile", {
            method: "PUT",
            headers: { "Content-Type": "application/json", "Authorization": `Bearer ${getToken()}` },
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

    async function savePassword() {
        if (pwForm.new_password !== pwForm.confirm) {
            showError("两次密码不一致");
            return;
        }
        const res = await fetch("/api/auth/password", {
            method: "PUT",
            headers: { "Content-Type": "application/json", "Authorization": `Bearer ${getToken()}` },
            body: JSON.stringify({
                old_password: pwForm.old_password,
                new_password: pwForm.new_password,
            }),
        });
        if (res.ok) {
            showMsg("密码修改成功");
            setPwForm({ old_password: "", new_password: "", confirm: "" });
        } else {
            const err = await res.json();
            showError(err.detail || "修改失败");
        }
    }

    async function saveSettings() {
        if (!settings) return;
        const res = await fetch("/api/settings/user", {
            method: "PUT",
            headers: { "Content-Type": "application/json", "Authorization": `Bearer ${getToken()}` },
            body: JSON.stringify({ settings }),
        });
        if (res.ok) showMsg("设置已保存");
        else showError("保存失败");
    }

    async function toggleUser(userId: string) {
        const res = await fetch(`/api/users/${userId}/toggle`, {
            method: "PUT",
            headers: { "Authorization": `Bearer ${getToken()}` },
        });
        if (res.ok) { loadUsers(); showMsg("操作成功"); }
        else showError("操作失败");
    }

    async function toggleAdmin(userId: string) {
        const res = await fetch(`/api/users/${userId}/admin`, {
            method: "PUT",
            headers: { "Authorization": `Bearer ${getToken()}` },
        });
        if (res.ok) { loadUsers(); showMsg("操作成功"); }
        else showError("操作失败");
    }

    const tabs: { key: Tab; label: string }[] = [
        { key: "profile", label: "个人资料" },
        { key: "password", label: "修改密码" },
        { key: "model", label: "模型设置" },
        ...(isAdmin ? [
            { key: "admin" as Tab, label: "用户管理" },
            { key: "audit" as Tab, label: "审计日志" },
        ] : []),
    ];

    return (
        <div className="p-8 max-w-3xl">
            <h1 className="text-2xl font-semibold text-white mb-6">设置</h1>

            {/* Tab 切换 */}
            <div className="flex gap-1 bg-gray-900 border border-gray-800 rounded-lg p-1 mb-6 w-fit">
                {tabs.map(t => (
                    <button
                        key={t.key}
                        onClick={() => setTab(t.key)}
                        className={`px-4 py-1.5 rounded text-sm transition-colors ${tab === t.key
                            ? "bg-indigo-600 text-white"
                            : "text-gray-400 hover:text-white"
                            }`}
                    >
                        {t.label}
                    </button>
                ))}
            </div>

            {/* 消息提示 */}
            {msg && <div className="mb-4 px-3 py-2 bg-green-500/10 border border-green-500/30 rounded-lg text-sm text-green-400">{msg}</div>}
            {error && <div className="mb-4 px-3 py-2 bg-red-500/10   border border-red-500/30   rounded-lg text-sm text-red-400"  >{error}</div>}

            {/* 个人资料 */}
            {tab === "profile" && profile && (
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
                    <button onClick={saveProfile}
                        className="px-5 py-2 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-500">
                        保存
                    </button>
                </div>
            )}

            {/* 修改密码 */}
            {tab === "password" && (
                <div className="space-y-4 bg-gray-900 rounded-xl p-5 border border-gray-800">
                    {[
                        { key: "old_password", label: "原密码", placeholder: "请输入原密码" },
                        { key: "new_password", label: "新密码", placeholder: "至少6位" },
                        { key: "confirm", label: "确认新密码", placeholder: "再次输入新密码" },
                    ].map(field => (
                        <div key={field.key}>
                            <label className="text-xs text-gray-500 mb-1 block">{field.label}</label>
                            <input type="password"
                                value={pwForm[field.key as keyof typeof pwForm]}
                                onChange={e => setPwForm(f => ({ ...f, [field.key]: e.target.value }))}
                                placeholder={field.placeholder}
                                className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded text-sm text-gray-200 outline-none focus:border-indigo-500" />
                        </div>
                    ))}
                    <button onClick={savePassword}
                        className="px-5 py-2 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-500">
                        修改密码
                    </button>
                </div>
            )}

            {/* 模型设置 */}
            {tab === "model" && settings && (
                <div className="space-y-6">
                    <div className="bg-gray-900 rounded-xl p-5 border border-gray-800">
                        <div className="text-xs text-gray-500 uppercase tracking-wider mb-4">Embedding 模型</div>
                        <div className="flex gap-2 mb-4">
                            {["local", "api"].map(mode => (
                                <button key={mode}
                                    onClick={() => setSettings(s => s ? { ...s, embedding_mode: mode } : s)}
                                    className={`px-3 py-1.5 rounded text-xs border transition-colors ${settings.embedding_mode === mode
                                        ? "bg-indigo-600 border-indigo-600 text-white"
                                        : "border-gray-700 text-gray-400 hover:border-gray-500"
                                        }`}>
                                    {mode === "local" ? "本地模型" : "API 模式"}
                                </button>
                            ))}
                        </div>
                        {settings.embedding_mode === "local" ? (
                            <div>
                                <label className="text-xs text-gray-500 mb-1 block">模型路径</label>
                                <input value={settings.embedding_model}
                                    onChange={e => setSettings(s => s ? { ...s, embedding_model: e.target.value } : s)}
                                    className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded text-sm text-gray-200 outline-none focus:border-indigo-500" />
                            </div>
                        ) : (
                            <div className="space-y-3">
                                {[
                                    { key: "embedding_api_url", label: "API 地址", placeholder: "https://api.openai.com/v1" },
                                    { key: "embedding_api_key", label: "API Key", placeholder: "sk-..." },
                                    { key: "embedding_model", label: "模型名称", placeholder: "text-embedding-3-small" },
                                ].map(f => (
                                    <div key={f.key}>
                                        <label className="text-xs text-gray-500 mb-1 block">{f.label}</label>
                                        <input value={settings[f.key as keyof ModelSettings]}
                                            onChange={e => setSettings(s => s ? { ...s, [f.key]: e.target.value } : s)}
                                            placeholder={f.placeholder}
                                            className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded text-sm text-gray-200 outline-none focus:border-indigo-500" />
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>

                    <div className="bg-gray-900 rounded-xl p-5 border border-gray-800">
                        <div className="text-xs text-gray-500 uppercase tracking-wider mb-4">查询配置</div>
                        <div className="space-y-4">
                            <div>
                                <label className="text-xs text-gray-500 mb-2 block">默认检索策略</label>
                                <div className="flex gap-2 flex-wrap">
                                    {["parallel", "sequential", "graph_augmented", "multi_hop"].map(s => (
                                        <button key={s}
                                            onClick={() => setSettings(prev => prev ? { ...prev, query_strategy: s } : prev)}
                                            className={`px-3 py-1.5 rounded text-xs border transition-colors ${settings.query_strategy === s
                                                ? "bg-indigo-600 border-indigo-600 text-white"
                                                : "border-gray-700 text-gray-400 hover:border-gray-500"
                                                }`}>
                                            {s}
                                        </button>
                                    ))}
                                </div>
                            </div>
                            <div>
                                <label className="text-xs text-gray-500 mb-2 block">
                                    返回章节数量：{settings.query_top_k}
                                </label>
                                <input type="range" min="3" max="10"
                                    value={settings.query_top_k}
                                    onChange={e => setSettings(s => s ? { ...s, query_top_k: e.target.value } : s)}
                                    className="w-full accent-indigo-600" />
                            </div>
                        </div>
                    </div>

                    <button onClick={saveSettings}
                        className="px-5 py-2 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-500">
                        保存设置
                    </button>
                </div>
            )}

            {/* 用户管理（仅管理员） */}
            {tab === "admin" && (
                <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="border-b border-gray-800 text-gray-400 text-left">
                                <th className="px-4 py-3">工号</th>
                                <th className="px-4 py-3">姓名</th>
                                <th className="px-4 py-3">部门</th>
                                <th className="px-4 py-3">状态</th>
                                <th className="px-4 py-3">操作</th>
                            </tr>
                        </thead>
                        <tbody>
                            {users.map(u => (
                                <tr key={u.user_id} className="border-b border-gray-800/50">
                                    <td className="px-4 py-3 font-mono text-gray-300">{u.username}</td>
                                    <td className="px-4 py-3 text-gray-300">
                                        {u.full_name}
                                        {u.is_admin && (
                                            <span className="ml-2 px-1.5 py-0.5 bg-indigo-500/20 text-indigo-400 text-xs rounded">
                                                管理员
                                            </span>
                                        )}
                                    </td>
                                    <td className="px-4 py-3 text-gray-400">{u.department}</td>
                                    <td className="px-4 py-3">
                                        <span className={`px-2 py-0.5 rounded text-xs ${u.is_active
                                            ? "bg-green-500/20 text-green-400"
                                            : "bg-red-500/20 text-red-400"
                                            }`}>
                                            {u.is_active ? "启用" : "禁用"}
                                        </span>
                                    </td>
                                    <td className="px-4 py-3">
                                        <div className="flex gap-2">
                                            <button onClick={() => toggleUser(u.user_id)}
                                                className="px-2 py-1 bg-gray-800 text-gray-400 text-xs rounded hover:text-white">
                                                {u.is_active ? "禁用" : "启用"}
                                            </button>
                                            <button onClick={() => toggleAdmin(u.user_id)}
                                                className="px-2 py-1 bg-gray-800 text-gray-400 text-xs rounded hover:text-white">
                                                {u.is_admin ? "撤销管理员" : "设为管理员"}
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}

            {/* 审计 */}
            {tab === "audit" && (
                <div>
                    <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden mb-4">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="border-b border-gray-800 text-gray-400 text-left">
                                    <th className="px-4 py-3">时间</th>
                                    <th className="px-4 py-3">用户</th>
                                    <th className="px-4 py-3">操作</th>
                                    <th className="px-4 py-3">详情</th>
                                </tr>
                            </thead>
                            <tbody>
                                {auditLogs.map(log => (
                                    <tr key={log.id} className="border-b border-gray-800/50">
                                        <td className="px-4 py-2.5 text-xs text-gray-500 whitespace-nowrap">
                                            {new Date(log.created_at).toLocaleString("zh-CN")}
                                        </td>
                                        <td className="px-4 py-2.5 text-xs text-gray-300">
                                            {log.full_name || log.username}
                                        </td>
                                        <td className="px-4 py-2.5">
                                            <span className={`px-2 py-0.5 rounded text-xs ${log.action === "login" ? "bg-green-500/20 text-green-400" :
                                                    log.action === "register" ? "bg-indigo-500/20 text-indigo-400" :
                                                        log.action.includes("delete") ? "bg-red-500/20 text-red-400" :
                                                            "bg-gray-700 text-gray-400"
                                                }`}>
                                                {log.action}
                                            </span>
                                        </td>
                                        <td className="px-4 py-2.5 text-xs text-gray-400">{log.detail}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>

                    {/* 分页 */}
                    <div className="flex items-center gap-2">
                        <button
                            onClick={() => loadAuditLogs(auditPage - 1)}
                            disabled={auditPage === 1}
                            className="px-3 py-1.5 bg-gray-900 border border-gray-700 rounded
                   text-xs text-gray-400 disabled:opacity-40"
                        >
                            上一页
                        </button>
                        <span className="text-xs text-gray-500">
                            共 {auditTotal} 条
                        </span>
                        <button
                            onClick={() => loadAuditLogs(auditPage + 1)}
                            disabled={auditLogs.length < 15}
                            className="px-3 py-1.5 bg-gray-900 border border-gray-700 rounded
                   text-xs text-gray-400 disabled:opacity-40"
                        >
                            下一页
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}