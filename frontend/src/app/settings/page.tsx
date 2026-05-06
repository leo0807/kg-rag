"use client";

import { useState, useEffect } from "react";
import { Tab } from "./types";
import { ProfileTab }  from "./ProfileTab";
import { PasswordTab } from "./PasswordTab";
import { ModelTab }    from "./ModelTab";
import { AdminTab }    from "./AdminTab";
import { AuditTab }    from "./AuditTab";
import { SearchTab }        from "./SearchTab";
import { EntityFilterTab }  from "./EntityFilterTab";
import { AlertTab }         from "./AlertTab";

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

    const tabs: { key: Tab; label: string; desc: string }[] = [
        { key: "profile",  label: "个人资料", desc: "编辑姓名、部门与邮箱" },
        { key: "password", label: "修改密码", desc: "更新你的登录凭证" },
        { key: "model",    label: "模型设置", desc: "配置默认模型与参数" },
        ...(isAdmin ? [
            { key: "admin"  as Tab, label: "用户管理",  desc: "创建与管理系统用户" },
            { key: "audit"  as Tab, label: "审计日志",  desc: "查看关键操作记录" },
            { key: "search"        as Tab, label: "检索配置",  desc: "混合检索 alpha 权重" },
            { key: "entity_filter" as Tab, label: "实体过滤",  desc: "黑白名单控制检索权重" },
            { key: "alert"         as Tab, label: "告警推送",  desc: "钉钉/企微 Webhook 配置" },
        ] : []),
    ];

    const active = tabs.find(t => t.key === tab);

    return (
        <div className="p-8 max-w-6xl mx-auto">
            <div className="mb-8">
                <h1 className="text-2xl font-semibold text-white">设置</h1>
                <p className="text-sm text-gray-500 mt-1">管理账号信息、模型参数与系统配置</p>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-[240px_1fr] gap-6">
                {/* 左侧导航 */}
                <aside className="bg-gray-950 border border-gray-800 rounded-xl p-3 h-fit">
                    <div className="text-xs text-gray-500 uppercase tracking-wider px-2 pb-2">设置项目</div>
                    <div className="space-y-1">
                        {tabs.map(t => (
                            <button key={t.key} onClick={() => setTab(t.key)}
                                className={`w-full text-left px-3 py-2 rounded-lg transition-colors ${
                                    tab === t.key
                                        ? "bg-indigo-600/20 text-white border border-indigo-600/40"
                                        : "text-gray-400 hover:text-white hover:bg-gray-900 border border-transparent"
                                }`}>
                                <div className="text-sm font-medium">{t.label}</div>
                                <div className="text-xs text-gray-500 mt-0.5">{t.desc}</div>
                            </button>
                        ))}
                    </div>
                </aside>

                {/* 右侧内容 */}
                <section className="space-y-4">
                    <div className="bg-gray-950 border border-gray-800 rounded-xl px-5 py-4">
                        <div className="text-sm font-semibold text-white">{active?.label}</div>
                        <div className="text-xs text-gray-500 mt-0.5">{active?.desc}</div>
                    </div>

                    {msg   && <div className="px-3 py-2 bg-green-500/10 border border-green-500/30 rounded-lg text-sm text-green-400">{msg}</div>}
                    {error && <div className="px-3 py-2 bg-red-500/10 border border-red-500/30 rounded-lg text-sm text-red-400">{error}</div>}

                    {tab === "profile"  && <ProfileTab  showMsg={showMsg} showError={showError} />}
                    {tab === "password" && <PasswordTab showMsg={showMsg} showError={showError} />}
                    {tab === "model"    && <ModelTab    showMsg={showMsg} showError={showError} />}
                    {tab === "admin"    && <AdminTab    showMsg={showMsg} showError={showError} />}
                    {tab === "audit"    && <AuditTab />}
                    {tab === "search"        && <SearchTab   showMsg={showMsg} showError={showError} />}
                    {tab === "entity_filter" && <EntityFilterTab />}
                    {tab === "alert"         && <AlertTab showMsg={showMsg} showError={showError} />}
                </section>
            </div>
        </div>
    );
}
