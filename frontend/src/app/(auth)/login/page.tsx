"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { BrainCircuit, Eye, EyeOff, X } from "lucide-react";

export default function LoginPage() {
    const router = useRouter();
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const [showPw, setShowPw] = useState(false);
    const [rememberMe, setRememberMe] = useState(false);
    const [rememberMsg, setRememberMsg] = useState("");
    const [showForgot, setShowForgot] = useState(false);

    const [form, setForm] = useState({ username: "", password: "" });

    // 恢复记住的工号
    useEffect(() => {
        const saved = localStorage.getItem("remembered_username");
        if (saved) {
            setForm(f => ({ ...f, username: saved }));
            setRememberMe(true);
        }
    }, []);

    async function handleLogin() {
        setLoading(true);
        setError("");
        try {
            const res = await fetch("/api/auth/login", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ username: form.username, password: form.password }),
            });
            const data = await res.json();
            if (!res.ok) {
                setError(data.detail || "登录失败，请重试");
                return;
            }
            if (rememberMe) {
                localStorage.setItem("remembered_username", form.username);
            } else {
                localStorage.removeItem("remembered_username");
            }
            localStorage.setItem("token", data.access_token);
            localStorage.setItem("user", JSON.stringify(data));
            router.push("/query");
        } finally {
            setLoading(false);
        }
    }

    function handleRememberToggle(checked: boolean) {
        setRememberMe(checked);
        if (checked) {
            setRememberMsg("已开启记住工号 — 下次访问将自动填入工号，密码不会被保存");
            setTimeout(() => setRememberMsg(""), 5000);
        } else {
            setRememberMsg("");
        }
    }

    return (
        <div className="min-h-screen bg-gradient-to-br from-[#F4F7FC] to-[#EBF1F8] dark:bg-[#050813] dark:bg-none relative flex items-start justify-center pt-8 px-4 sm:items-center sm:pt-0">

            {/* 背景光晕（日间：淡蓝，深色：原有深蓝紫） */}
            <div className="absolute inset-0 pointer-events-none overflow-hidden">
                <div className="absolute -top-72 -left-72 w-[600px] h-[600px] bg-[#1B6BB5]/8 dark:bg-indigo-700/20 rounded-full blur-[140px]" />
                <div className="absolute -bottom-72 -right-48 w-[600px] h-[600px] bg-[#1B4F9B]/6 dark:bg-violet-700/15 rounded-full blur-[140px]" />
                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-[#1B6BB5]/5 dark:bg-blue-600/8 rounded-full blur-[100px]" />
            </div>

            {/* 网格背景 */}
            <div
                className="absolute inset-0 pointer-events-none"
                style={{
                    backgroundImage:
                        "linear-gradient(rgba(27,107,181,0.06) 1px, transparent 1px), linear-gradient(90deg, rgba(27,107,181,0.06) 1px, transparent 1px)",
                    backgroundSize: "48px 48px",
                }}
            />

            {/* 浮动节点装饰 */}
            <div className="absolute inset-0 pointer-events-none overflow-hidden">
                {[
                    { x: "12%", y: "18%", delay: "0s" },
                    { x: "85%", y: "22%", delay: "0.8s" },
                    { x: "72%", y: "72%", delay: "1.4s" },
                    { x: "20%", y: "78%", delay: "0.4s" },
                    { x: "50%", y: "12%", delay: "1.8s" },
                    { x: "38%", y: "88%", delay: "1.1s" },
                ].map((dot, i) => (
                    <div
                        key={i}
                        className="absolute w-1.5 h-1.5 bg-indigo-400/25 rounded-full"
                        style={{
                            left: dot.x,
                            top: dot.y,
                            animation: `pulse 3s ease-in-out ${dot.delay} infinite`,
                        }}
                    />
                ))}
                <svg className="absolute inset-0 w-full h-full opacity-5" xmlns="http://www.w3.org/2000/svg">
                    <line x1="12%" y1="18%" x2="50%" y2="12%" stroke="#818cf8" strokeWidth="0.5" />
                    <line x1="50%" y1="12%" x2="85%" y2="22%" stroke="#818cf8" strokeWidth="0.5" />
                    <line x1="12%" y1="18%" x2="20%" y2="78%" stroke="#818cf8" strokeWidth="0.5" />
                    <line x1="85%" y1="22%" x2="72%" y2="72%" stroke="#818cf8" strokeWidth="0.5" />
                    <line x1="20%" y1="78%" x2="38%" y2="88%" stroke="#818cf8" strokeWidth="0.5" />
                    <line x1="72%" y1="72%" x2="38%" y2="88%" stroke="#818cf8" strokeWidth="0.5" />
                </svg>
            </div>

            {/* 主内容 */}
            <div className="relative z-10 w-full max-w-sm">

                {/* Logo 区域 */}
                <div className="text-center mb-5 sm:mb-8">
                    <div className="inline-flex items-center justify-center w-16 h-16
                                    bg-[#1B6BB5]/15 border border-[#1B6BB5]/30 rounded-2xl mb-5
                                    shadow-lg shadow-[#1B6BB5]/10">
                        <BrainCircuit size={30} className="text-[#1B6BB5]" />
                    </div>
                    <div className="text-xs font-semibold tracking-widest uppercase text-[#1B6BB5] mb-1">COMAC</div>
                    <h1 className="text-2xl font-bold text-[#1A2F4A] dark:text-white tracking-tight">航空工艺知识库系统</h1>
                    <p className="text-sm text-[#6B8BAE] dark:text-gray-500 mt-1.5 tracking-wide">CPS 规范智能检索与问答平台</p>
                    <div className="inline-flex items-center gap-1.5 mt-3 px-2.5 py-1
                                    bg-emerald-500/10 border border-emerald-500/20 rounded-full">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                        <span className="text-xs text-emerald-400/80">系统在线</span>
                    </div>
                </div>

                {/* 忘记密码面板 */}
                {showForgot && (
                    <div className="mb-5 bg-amber-950/30 border border-amber-700/40 rounded-2xl p-5 relative">
                        <button
                            onClick={() => setShowForgot(false)}
                            className="absolute top-3 right-3 text-gray-500 hover:text-white transition-colors"
                        >
                            <X size={14} />
                        </button>
                        <div className="text-sm font-semibold text-amber-300 mb-2">如何重置密码？</div>
                        <p className="text-xs text-gray-300 leading-relaxed mb-3">
                            本系统不支持自助找回密码。请联系系统管理员，提供您的
                            <span className="text-amber-300 font-medium">工号（员工ID）</span>，
                            由管理员在后台为您重置临时密码。
                        </p>
                        <div className="text-xs text-gray-500 space-y-1">
                            <div>① 告知管理员您的 6 位工号</div>
                            <div>② 管理员通过「设置 → 用户管理 → 重置密码」操作</div>
                            <div>③ 登录后请立即前往「设置 → 修改密码」更改临时密码</div>
                        </div>
                    </div>
                )}

                {/* 登录卡片 */}
                <div className="bg-white/90 dark:bg-gray-900/60 backdrop-blur-md border border-[#D4E2F0] dark:border-gray-700/40
                                rounded-2xl p-5 sm:p-7 shadow-xl shadow-[#1B6BB5]/8 dark:shadow-black/60">

                    <h2 className="text-sm font-semibold text-[#3D5A7A] dark:text-gray-300 mb-5 tracking-wide uppercase">
                        账号登录
                    </h2>

                    {/* 错误提示 */}
                    {error && (
                        <div className="mb-5 px-3 py-2.5 bg-red-500/10 border border-red-500/25
                                        rounded-lg text-sm text-red-400 flex items-center gap-2">
                            <span className="shrink-0">⚠</span>
                            <span>{error}</span>
                        </div>
                    )}

                    {/* 记住我提示 */}
                    {rememberMsg && (
                        <div className="mb-5 px-3 py-2.5 bg-indigo-500/10 border border-indigo-500/25
                                        rounded-lg text-xs text-indigo-400 leading-relaxed">
                            {rememberMsg}
                        </div>
                    )}

                    <div className="space-y-4">
                        {/* 工号 */}
                        <div>
                            <label className="text-xs text-[#6B8BAE] dark:text-gray-500 mb-1.5 block">工号</label>
                            <input
                                value={form.username}
                                onChange={e => setForm(f => ({ ...f, username: e.target.value }))}
                                placeholder="请输入6位工号"
                                maxLength={6}
                                className="w-full px-3 py-2.5 bg-[#F4F7FC] dark:bg-gray-800/60 border border-[#D4E2F0] dark:border-gray-700/60
                                           rounded-lg text-sm text-[#1A2F4A] dark:text-gray-200 outline-none transition-colors
                                           focus:border-[#1B6BB5] dark:focus:bg-gray-800 placeholder-[#9BB3CC]"
                            />
                        </div>

                        {/* 密码 */}
                        <div>
                            <div className="flex items-center justify-between mb-1.5">
                                <label className="text-xs text-[#6B8BAE] dark:text-gray-500">密码</label>
                                <button
                                    type="button"
                                    onClick={() => setShowForgot(v => !v)}
                                    className="text-xs text-[#1B6BB5] hover:text-[#1558A0] transition-colors"
                                >
                                    忘记密码？
                                </button>
                            </div>
                            <div className="relative">
                                <input
                                    type={showPw ? "text" : "password"}
                                    value={form.password}
                                    onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
                                    placeholder="请输入密码"
                                    onKeyDown={e => e.key === "Enter" && handleLogin()}
                                    className="w-full pl-3 pr-10 py-2.5 bg-[#F4F7FC] dark:bg-gray-800/60 border border-[#D4E2F0] dark:border-gray-700/60
                                               rounded-lg text-sm text-[#1A2F4A] dark:text-gray-200 outline-none transition-colors
                                               focus:border-[#1B6BB5] dark:focus:bg-gray-800 placeholder-[#9BB3CC]"
                                />
                                <button
                                    type="button"
                                    onClick={() => setShowPw(v => !v)}
                                    className="absolute right-3 top-1/2 -translate-y-1/2
                                               text-gray-600 hover:text-gray-300 transition-colors"
                                >
                                    {showPw ? <EyeOff size={15} /> : <Eye size={15} />}
                                </button>
                            </div>
                        </div>

                        {/* 记住我 */}
                        <label className="flex items-center gap-2.5 cursor-pointer select-none group">
                            <div className="relative">
                                <input
                                    type="checkbox"
                                    checked={rememberMe}
                                    onChange={e => handleRememberToggle(e.target.checked)}
                                    className="sr-only"
                                />
                                <div className={`w-4 h-4 rounded border transition-colors flex items-center justify-center
                                    ${rememberMe
                                        ? "bg-indigo-600 border-indigo-600"
                                        : "bg-gray-800 border-gray-600 group-hover:border-gray-400"}`}>
                                    {rememberMe && (
                                        <svg width="9" height="7" viewBox="0 0 9 7" fill="none">
                                            <path d="M1 3.5L3.5 6L8 1" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                                        </svg>
                                    )}
                                </div>
                            </div>
                            <span className="text-xs text-gray-500 group-hover:text-gray-400 transition-colors">
                                记住工号
                            </span>
                        </label>

                        {/* 登录按钮 */}
                        <button
                            onClick={handleLogin}
                            disabled={loading || !form.username || !form.password}
                            className="w-full py-2.5 bg-[#1B6BB5] text-white text-sm rounded-lg font-medium
                                       hover:bg-[#1558A0] disabled:opacity-40 disabled:cursor-not-allowed
                                       transition-colors shadow-lg shadow-[#1B6BB5]/25 mt-2"
                        >
                            {loading ? (
                                <span className="flex items-center justify-center gap-2">
                                    <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white
                                                     rounded-full animate-spin inline-block" />
                                    登录中...
                                </span>
                            ) : "登 录"}
                        </button>
                    </div>
                </div>

                {/* 底部说明 */}
                <p className="text-center text-xs text-gray-600 mt-6 leading-relaxed">
                    新用户账号由系统管理员统一创建
                    <br />
                    如需开通访问权限，请联系管理员
                </p>
            </div>
        </div>
    );
}
