"use client";

import { useState, useEffect } from "react";
import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";
import { Eye, EyeOff, Shield, ChevronRight, BrainCircuit } from "lucide-react";
import ForgotPanel, { type ForgotState } from "./ForgotPanel";
import LoginInfoPanel from "./LoginInfoPanel";
import LoginBackdrop from "./LoginBackdrop";

const ParticleCanvas = dynamic(() => import("@/components/home/ParticleCanvas"), { ssr: false });
const FloatingData   = dynamic(() => import("@/components/home/FloatingData"),   { ssr: false });

export default function LoginPage() {
  const router = useRouter();
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState("");
  const [showPw, setShowPw]     = useState(false);
  const [showForgot, setShowForgot] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);
  const [form, setForm] = useState({ username: "", password: "" });
  const [tick, setTick] = useState("");
  const [forgotState, setForgotState] = useState<ForgotState>("idle");
  const [forgotMsg, setForgotMsg] = useState("");

  useEffect(() => {
    const saved = localStorage.getItem("remembered_username");
    if (saved) { setForm(f => ({ ...f, username: saved })); setRememberMe(true); }
  }, []);

  useEffect(() => {
    setTick(new Date().toLocaleTimeString("en-GB"));  // 首次渲染后立即同步
    const iv = setInterval(() => setTick(new Date().toLocaleTimeString("en-GB")), 1000);
    return () => clearInterval(iv);
  }, []);

  async function handleForgot() {
    if (!form.username) { setForgotMsg("请先填写工号"); setForgotState("error"); return; }
    setForgotState("loading");
    try {
      const res = await fetch("/api/auth/forgot-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: form.username }),
      });
      const data = await res.json();
      if (res.status === 429) { setForgotState("rate_limited"); setForgotMsg(data.detail || "申请已提交"); }
      else if (!res.ok)       { setForgotState("error");        setForgotMsg(data.detail || "发送失败，请稍后重试"); }
      else                    { setForgotState("sent");          setForgotMsg(data.detail || "申请已发送"); }
    } catch {
      setForgotState("error"); setForgotMsg("网络错误，请重试");
    }
  }

  async function handleLogin() {
    setLoading(true); setError("");
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
    } finally { setLoading(false); }
  }

  return (
    <div className="relative min-h-screen bg-gray-950 flex items-center justify-center px-4 overflow-hidden">
      <ParticleCanvas />
      <FloatingData />

      <LoginBackdrop />

      {/* ── Main card ───────────────────────── */}
      <div className="relative z-10 w-full max-w-4xl" style={{ animation: "page-enter 0.5s ease both" }}>
        {/* Glowing border wrapper */}
        <div className="relative rounded-2xl p-[1px]" style={{
          background: "linear-gradient(135deg,rgba(34,211,238,0.4),rgba(99,102,241,0.2),rgba(34,211,238,0.15))",
          backgroundSize: "200% 200%", animation: "gradient-sweep 5s ease infinite",
        }}>
          {/* Card scan line */}
          <div className="absolute inset-0 rounded-2xl overflow-hidden pointer-events-none z-20">
            <div className="absolute inset-x-0 h-[2px]" style={{
              background: "linear-gradient(90deg,transparent,rgba(34,211,238,0.5) 50%,transparent)",
              animation: "scan-down 5s linear infinite",
            }} />
          </div>

          <div className="relative bg-gray-950/95 backdrop-blur-xl rounded-[15px] overflow-hidden grid grid-cols-1 lg:grid-cols-[360px_1fr]">

            {/* ── LEFT INFO PANEL ──────────────── */}
            <LoginInfoPanel tick={tick} />

            {/* ── RIGHT FORM PANEL ─────────────── */}
            <div className="p-8 flex flex-col justify-center">
              {/* Mobile logo (only on small screens) */}
              <div className="lg:hidden text-center mb-6">
                <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-gray-900 border border-cyan-500/40 mb-3"
                     style={{ boxShadow: "0 0 24px rgba(34,211,238,0.18)" }}>
                  <BrainCircuit size={22} className="text-cyan-400" />
                </div>
                <h1 className="text-xl font-bold text-white">航空工艺知识库系统</h1>
              </div>

              {/* Section label */}
              <div className="flex items-center gap-2 mb-4">
                <Shield size={12} className="text-cyan-400/60" />
                <span className="text-[10px] font-mono text-gray-600 tracking-[0.2em] uppercase">身份验证</span>
                <div className="flex-1 h-px bg-gradient-to-r from-gray-700/60 to-transparent" />
                <span className="text-[9px] font-mono text-gray-700">访问控制</span>
              </div>

              {/* Connection status row */}
              <div className="flex items-center gap-3 mb-5 px-2 py-1.5 rounded-lg border"
                   style={{ background: "rgba(2,8,20,0.5)", borderColor: "rgba(34,211,238,0.08)" }}>
                {[
                  { dot: "#4ade80", label: "AUTH_SVC" },
                  { dot: "#60a5fa", label: "NEO4J" },
                  { dot: "#a78bfa", label: "LLM_API" },
                  { dot: "#22d3ee", label: "TLS_1.3" },
                ].map(({ dot, label }) => (
                  <span key={label} className="flex items-center gap-1 text-[8px] font-mono text-gray-700">
                    <span className="w-1 h-1 rounded-full animate-pulse" style={{ background: dot, boxShadow: `0 0 4px ${dot}` }} />
                    {label}
                  </span>
                ))}
              </div>

              {/* Forgot panel */}
              {showForgot && (
                <ForgotPanel
                  state={forgotState}
                  msg={forgotMsg}
                  username={form.username}
                  onClose={() => { setShowForgot(false); setForgotState("idle"); setForgotMsg(""); }}
                  onSubmit={handleForgot}
                />
              )}

              {/* Error */}
              {error && (
                <div className="mb-4 px-3 py-2.5 bg-red-500/8 border border-red-500/20 rounded-lg text-sm text-red-400 flex items-center gap-2 font-mono"
                     style={{ animation: "scale-fade 0.2s ease both" }}>
                  <span className="text-red-500">▲</span><span>{error}</span>
                </div>
              )}

              <div className="space-y-4">
                {/* Username */}
                <div>
                  <label className="text-[10px] font-mono text-gray-600 mb-1.5 block tracking-widest">工号</label>
                  <input
                    value={form.username}
                    onChange={e => setForm(f => ({ ...f, username: e.target.value.replace(/\D/g, "") }))}
                    inputMode="numeric"
                    placeholder="输入 6 位工号"
                    maxLength={6}
                    className="w-full px-3 py-3 bg-gray-900/70 border border-gray-700/60 rounded-xl text-sm text-gray-200 outline-none placeholder-gray-700 transition-all font-mono focus:border-cyan-500/60 focus:bg-gray-900 focus:shadow-[0_0_16px_rgba(34,211,238,0.08)]"
                  />
                  {form.username.length > 0 && form.username.length < 6 && (
                    <p className="mt-1 text-[10px] font-mono text-amber-500/80">
                      工号须为 6 位数字（已输入 {form.username.length} 位）
                    </p>
                  )}
                </div>

                {/* Password */}
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <label className="text-[10px] font-mono text-gray-600 tracking-widest">密码</label>
                    <button type="button" onClick={() => setShowForgot(v => !v)}
                      className="text-[10px] font-mono text-cyan-400/50 hover:text-cyan-400 transition-colors">
                      忘记密码？
                    </button>
                  </div>
                  <div className="relative">
                    <input
                      type={showPw ? "text" : "password"}
                      value={form.password}
                      onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
                      placeholder="输入密码"
                      onKeyDown={e => e.key === "Enter" && handleLogin()}
                      className="w-full pl-3 pr-10 py-3 bg-gray-900/70 border border-gray-700/60 rounded-xl text-sm text-gray-200 outline-none placeholder-gray-700 transition-all font-mono focus:border-cyan-500/60 focus:bg-gray-900 focus:shadow-[0_0_16px_rgba(34,211,238,0.08)]"
                    />
                    <button type="button" onClick={() => setShowPw(v => !v)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-600 hover:text-gray-300 transition-colors">
                      {showPw ? <EyeOff size={14} /> : <Eye size={14} />}
                    </button>
                  </div>
                </div>

                {/* Remember */}
                <label className="flex items-center gap-2.5 cursor-pointer select-none group">
                  <div className="relative" onClick={() => setRememberMe(v => !v)}>
                    <div className={`w-4 h-4 rounded border transition-all flex items-center justify-center
                      ${rememberMe ? "bg-cyan-600 border-cyan-500 shadow-[0_0_8px_rgba(34,211,238,0.35)]" : "bg-gray-800 border-gray-700 group-hover:border-gray-500"}`}>
                      {rememberMe && <svg width="9" height="7" viewBox="0 0 9 7" fill="none"><path d="M1 3.5L3.5 6L8 1" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>}
                    </div>
                  </div>
                  <span className="text-[10px] font-mono text-gray-600 group-hover:text-gray-400 transition-colors">记住工号</span>
                </label>

                {/* Submit */}
                <button
                  onClick={handleLogin}
                  disabled={loading || !form.username || !form.password}
                  className="relative w-full py-3 text-white text-sm rounded-xl font-bold transition-all mt-2 overflow-hidden disabled:opacity-40 disabled:cursor-not-allowed hover:brightness-110 active:scale-[0.98] tracking-widest font-mono"
                  style={{
                    background: "linear-gradient(135deg,#0891b2 0%,#2563eb 50%,#6366f1 100%)",
                    boxShadow: "0 0 24px rgba(34,211,238,0.2)",
                    clipPath: "polygon(8px 0%,100% 0%,calc(100% - 8px) 100%,0% 100%)",
                  }}
                >
                  <span className="absolute inset-0 pointer-events-none"
                    style={{ background: "linear-gradient(90deg,transparent,rgba(255,255,255,0.1) 50%,transparent)", backgroundSize: "200% 100%", animation: "shine 2.5s linear infinite" }} />
                  <span className="absolute inset-x-0 h-[1px]"
                    style={{ background: "linear-gradient(90deg,transparent,rgba(255,255,255,0.5),transparent)", animation: "scan-down 4s linear infinite" }} />
                  {loading ? (
                    <span className="flex items-center justify-center gap-2">
                      <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                      AUTHENTICATING...
                    </span>
                  ) : (
                    <span className="flex items-center justify-center gap-2">
                      [ 进入系统 ] <ChevronRight size={14} />
                    </span>
                  )}
                </button>
              </div>

              <div className="mt-5 border-t pt-4 space-y-1" style={{ borderColor: "rgba(255,255,255,0.04)" }}>
                <p className="text-center text-[10px] font-mono text-gray-700">新用户账号由系统管理员统一创建</p>
                <p className="text-center text-[8px] font-mono text-gray-800 tracking-widest">
                  ALL ACCESS LOGGED · 0 ANONYMOUS SESSIONS · AES-256-GCM
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
