"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { BrainCircuit, Eye, EyeOff, X, Shield } from "lucide-react";
import ParticleCanvas from "@/components/home/ParticleCanvas";

export default function LoginPage() {
    const router = useRouter();
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const [showPw, setShowPw] = useState(false);
    const [rememberMe, setRememberMe] = useState(false);
    const [rememberMsg, setRememberMsg] = useState("");
    const [showForgot, setShowForgot] = useState(false);
    const [form, setForm] = useState({ username: "", password: "" });

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
            if (!res.ok) { setError(data.detail || "登录失败，请重试"); return; }
            if (rememberMe) localStorage.setItem("remembered_username", form.username);
            else localStorage.removeItem("remembered_username");
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
        <div className="relative min-h-screen bg-gray-950 flex items-center justify-center px-4 overflow-hidden">
            <ParticleCanvas />

            {/* cyan grid overlay */}
            <div className="absolute inset-0 pointer-events-none" style={{
                backgroundImage: "linear-gradient(rgba(34,211,238,0.035) 1px,transparent 1px),linear-gradient(90deg,rgba(34,211,238,0.035) 1px,transparent 1px)",
                backgroundSize: "48px 48px",
            }} />

            {/* ambient glows */}
            <div className="absolute inset-0 pointer-events-none overflow-hidden">
                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-cyan-500/5 rounded-full blur-[120px]" />
                <div className="absolute top-1/4 right-1/4 w-72 h-72 bg-blue-600/6 rounded-full blur-[80px]" />
                <div className="absolute bottom-1/4 left-1/4 w-64 h-64 bg-indigo-600/5 rounded-full blur-[80px]" />
            </div>

            {/* main content */}
            <div className="relative z-10 w-full max-w-sm" style={{ animation: "slide-up-fade 0.5s ease both" }}>

                {/* logo */}
                <div className="text-center mb-7">
                    <div className="relative inline-flex items-center justify-center w-20 h-20 mb-5">
                        <div className="absolute inset-0 border border-cyan-500/25 rounded-full" style={{ animation: "spin-slow 12s linear infinite" }} />
                        <div className="absolute inset-1 border border-cyan-400/15 rounded-full" style={{ animation: "spin-slow 8s linear infinite reverse" }} />
                        <span className="absolute inset-0 rounded-full border border-cyan-400/30" style={{ animation: "pulse-ring 2.4s ease-out infinite" }} />
                        <div className="relative z-10 w-14 h-14 rounded-2xl bg-gray-900 border border-cyan-500/40 flex items-center justify-center"
                            style={{ boxShadow: "0 0 24px rgba(34,211,238,0.18),inset 0 0 12px rgba(34,211,238,0.05)" }}>
                            <BrainCircuit size={26} className="text-cyan-400" />
                        </div>
                    </div>

                    <div className="text-[10px] font-bold tracking-[0.28em] text-cyan-400/60 uppercase mb-2">
                        COMAC · 商用飞机有限责任公司
                    </div>
                    <h1 className="text-2xl font-bold mb-1.5" style={{
                        backgroundImage: "linear-gradient(135deg,#e2e8f0 0%,#38bdf8 45%,#818cf8 100%)",
                        backgroundClip: "text", WebkitBackgroundClip: "text", color: "transparent",
                        backgroundSize: "200% 200%", animation: "gradient-sweep 5s ease infinite",
                    }}>
                        航空工艺知识库系统
                    </h1>
                    <p className="text-sm text-gray-600">CPS 规范智能检索与问答平台</p>

                    <div className="inline-flex items-center gap-1.5 mt-3 px-3 py-1 bg-emerald-500/10 border border-emerald-500/20 rounded-full">
                        <span className="relative flex h-1.5 w-1.5">
                            <span className="absolute inline-flex h-full w-full rounded-full bg-emerald-400/70" style={{ animation: "pulse-ring 1.8s ease-out infinite" }} />
                            <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-emerald-400" />
                        </span>
                        <span className="text-xs text-emerald-400/80">系统在线</span>
                    </div>
                </div>

                {/* forgot password panel */}
                {showForgot && (
                    <div className="mb-5 bg-amber-950/30 border border-amber-700/30 rounded-2xl p-5 relative"
                        style={{ animation: "slide-up-fade 0.22s ease both" }}>
                        <button onClick={() => setShowForgot(false)}
                            className="absolute top-3 right-3 text-gray-600 hover:text-gray-300 transition-colors">
                            <X size={14} />
                        </button>
                        <div className="text-sm font-semibold text-amber-300 mb-2">如何重置密码？</div>
                        <p className="text-xs text-gray-400 leading-relaxed mb-3">
                            请联系系统管理员，提供您的<span className="text-amber-300 font-medium">工号（员工ID）</span>，由管理员在后台为您重置临时密码。
                        </p>
                        <div className="text-xs text-gray-600 space-y-1">
                            <div>① 告知管理员您的 6 位工号</div>
                            <div>② 管理员通过「设置 → 用户管理 → 重置密码」操作</div>
                            <div>③ 登录后请立即前往「设置 → 修改密码」更改临时密码</div>
                        </div>
                    </div>
                )}

                {/* card with animated gradient border */}
                <div className="relative rounded-2xl p-[1px]" style={{
                    background: "linear-gradient(135deg,rgba(34,211,238,0.5),rgba(99,102,241,0.25),rgba(34,211,238,0.5))",
                    backgroundSize: "200% 200%", animation: "gradient-sweep 4s ease infinite",
                }}>
                    {/* scan line */}
                    <div className="absolute inset-0 rounded-2xl overflow-hidden pointer-events-none z-20">
                        <div style={{
                            position: "absolute", left: 0, right: 0, height: "2px",
                            background: "linear-gradient(90deg,transparent 0%,rgba(34,211,238,0.55) 50%,transparent 100%)",
                            animation: "scan-down 5s linear infinite",
                        }} />
                    </div>

                    <div className="relative bg-gray-900/95 backdrop-blur-xl rounded-[15px] px-6 py-7">
                        {/* section label */}
                        <div className="flex items-center gap-2 mb-6">
                            <Shield size={12} className="text-cyan-400/60" />
                            <span className="text-[10px] font-semibold text-gray-500 tracking-[0.2em] uppercase">账号登录</span>
                            <div className="flex-1 h-px bg-gradient-to-r from-gray-700/80 to-transparent" />
                        </div>

                        {error && (
                            <div className="mb-4 px-3 py-2.5 bg-red-500/10 border border-red-500/20 rounded-lg text-sm text-red-400 flex items-center gap-2"
                                style={{ animation: "slide-up-fade 0.2s ease both" }}>
                                <span>⚠</span><span>{error}</span>
                            </div>
                        )}
                        {rememberMsg && (
                            <div className="mb-4 px-3 py-2.5 bg-indigo-500/10 border border-indigo-500/20 rounded-lg text-xs text-indigo-400 leading-relaxed">
                                {rememberMsg}
                            </div>
                        )}

                        <div className="space-y-4">
                            <div>
                                <label className="text-xs text-gray-600 mb-1.5 block">工号</label>
                                <input
                                    value={form.username}
                                    onChange={e => setForm(f => ({ ...f, username: e.target.value }))}
                                    placeholder="请输入6位工号"
                                    maxLength={6}
                                    className="w-full px-3 py-2.5 bg-gray-800/70 border border-gray-700/60 rounded-lg text-sm text-gray-200 outline-none placeholder-gray-700 transition-all focus:border-cyan-500/60 focus:bg-gray-800"
                                />
                            </div>

                            <div>
                                <div className="flex items-center justify-between mb-1.5">
                                    <label className="text-xs text-gray-600">密码</label>
                                    <button type="button" onClick={() => setShowForgot(v => !v)}
                                        className="text-xs text-cyan-400/60 hover:text-cyan-400 transition-colors">
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
                                        className="w-full pl-3 pr-10 py-2.5 bg-gray-800/70 border border-gray-700/60 rounded-lg text-sm text-gray-200 outline-none placeholder-gray-700 transition-all focus:border-cyan-500/60 focus:bg-gray-800"
                                    />
                                    <button type="button" onClick={() => setShowPw(v => !v)}
                                        className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-600 hover:text-gray-300 transition-colors">
                                        {showPw ? <EyeOff size={15} /> : <Eye size={15} />}
                                    </button>
                                </div>
                            </div>

                            <label className="flex items-center gap-2.5 cursor-pointer select-none group">
                                <div className="relative">
                                    <input type="checkbox" checked={rememberMe} onChange={e => handleRememberToggle(e.target.checked)} className="sr-only" />
                                    <div className={`w-4 h-4 rounded border transition-all flex items-center justify-center
                                        ${rememberMe ? "bg-cyan-600 border-cyan-500 shadow-[0_0_8px_rgba(34,211,238,0.35)]" : "bg-gray-800 border-gray-600 group-hover:border-gray-500"}`}>
                                        {rememberMe && <svg width="9" height="7" viewBox="0 0 9 7" fill="none"><path d="M1 3.5L3.5 6L8 1" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>}
                                    </div>
                                </div>
                                <span className="text-xs text-gray-600 group-hover:text-gray-400 transition-colors">记住工号</span>
                            </label>

                            <button
                                onClick={handleLogin}
                                disabled={loading || !form.username || !form.password}
                                className="relative w-full py-2.5 text-white text-sm rounded-lg font-medium transition-all mt-1 overflow-hidden disabled:opacity-40 disabled:cursor-not-allowed hover:brightness-110 active:scale-[0.98]"
                                style={{ background: "linear-gradient(135deg,#06b6d4,#3b82f6,#6366f1)" }}
                            >
                                <span className="absolute inset-0 pointer-events-none"
                                    style={{ background: "linear-gradient(90deg,transparent 0%,rgba(255,255,255,0.08) 50%,transparent 100%)", backgroundSize: "200% 100%", animation: "shine 3s linear infinite" }} />
                                {loading ? (
                                    <span className="flex items-center justify-center gap-2">
                                        <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin inline-block" />
                                        登录中...
                                    </span>
                                ) : "登 录"}
                            </button>
                        </div>
                    </div>
                </div>

                <p className="text-center text-xs text-gray-700 mt-6 leading-relaxed">
                    新用户账号由系统管理员统一创建<br />如需开通访问权限，请联系管理员
                </p>
            </div>
        </div>
    );
}
