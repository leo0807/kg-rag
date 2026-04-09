"use client";

import { useState, useEffect } from "react";
import { Tab } from "./types";
import { ProfileTab }  from "./ProfileTab";
import { PasswordTab } from "./PasswordTab";
import { ModelTab }    from "./ModelTab";
import { AdminTab }    from "./AdminTab";
import { AuditTab }    from "./AuditTab";

export default function SettingsPage() {
    const [tab, setTab]       = useState<Tab>("profile");
    const [isAdmin, setIsAdmin] = useState(false);
    const [msg,   setMsg]     = useState("");
    const [error, setError]   = useState("");

    useEffect(() => {
        const stored = localStorage.getItem("user");
        if (stored) {
            const u = JSON.parse(stored);
            setIsAdmin(u.is_admin ?? false);
        }
    }, []);

    function showMsg(m: string) {
        setMsg(m); setError("");
        setTimeout(() => setMsg(""), 3000);
    }

    function showError(e: string) {
        setError(e); setMsg("");
        setTimeout(() => setError(""), 3000);
    }

    const tabs: { key: Tab; label: string }[] = [
        { key: "profile",  label: "个人资料" },
        { key: "password", label: "修改密码" },
        { key: "model",    label: "模型设置" },
        ...(isAdmin ? [
            { key: "admin" as Tab, label: "用户管理" },
            { key: "audit" as Tab, label: "审计日志" },
        ] : []),
    ];

    return (
        <div className="p-8 max-w-3xl mx-auto">
            <h1 className="text-2xl font-semibold text-white mb-6">设置</h1>

            <div className="flex gap-1 bg-gray-900 border border-gray-800 rounded-lg p-1 mb-6 w-fit">
                {tabs.map(t => (
                    <button key={t.key} onClick={() => setTab(t.key)}
                        className={`px-4 py-1.5 rounded text-sm transition-colors ${tab === t.key
                            ? "bg-indigo-600 text-white"
                            : "text-gray-400 hover:text-white"
                        }`}>
                        {t.label}
                    </button>
                ))}
            </div>

            {msg   && <div className="mb-4 px-3 py-2 bg-green-500/10 border border-green-500/30 rounded-lg text-sm text-green-400">{msg}</div>}
            {error && <div className="mb-4 px-3 py-2 bg-red-500/10 border border-red-500/30 rounded-lg text-sm text-red-400">{error}</div>}

            {tab === "profile"  && <ProfileTab  showMsg={showMsg} showError={showError} />}
            {tab === "password" && <PasswordTab showMsg={showMsg} showError={showError} />}
            {tab === "model"    && <ModelTab    showMsg={showMsg} showError={showError} />}
            {tab === "admin"    && <AdminTab    showMsg={showMsg} showError={showError} />}
            {tab === "audit"    && <AuditTab />}
        </div>
    );
}
