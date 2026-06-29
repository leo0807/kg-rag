"use client";

import { useState, useEffect } from "react";
import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";
import { BrainCircuit, Eye, EyeOff, X, Shield, ChevronRight, Activity, Database, Network, Cpu } from "lucide-react";

const ParticleCanvas = dynamic(() => import("@/components/home/ParticleCanvas"), { ssr: false });
const FloatingData   = dynamic(() => import("@/components/home/FloatingData"),   { ssr: false });

const FEATURES = [
  { Icon: Network,   text: "GraphRAG 四策略混合检索" },
  { Icon: Database,  text: "Neo4j + Milvus 双库融合" },
  { Icon: Activity,  text: "LangGraph ReAct 多跳推理" },
  { Icon: Cpu,       text: "全链路 LLM 可观测性追踪" },
];

export default function LoginPage() {
  const router = useRouter();
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState("");
  const [showPw, setShowPw]     = useState(false);
  const [showForgot, setShowForgot] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);
  const [form, setForm] = useState({ username: "", password: "" });
  const [tick, setTick] = useState("");  // 空字符串避免 SSR/客户端时间不一致导致 hydration 错误

  useEffect(() => {
    const saved = localStorage.getItem("remembered_username");
    if (saved) { setForm(f => ({ ...f, username: saved })); setRememberMe(true); }
  }, []);

  useEffect(() => {
    setTick(new Date().toLocaleTimeString("en-GB"));  // 首次渲染后立即同步
    const iv = setInterval(() => setTick(new Date().toLocaleTimeString("en-GB")), 1000);
    return () => clearInterval(iv);
  }, []);

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

      {/* Hex grid */}
      <div className="absolute inset-0 pointer-events-none opacity-[0.05]" style={{
        backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='56' height='100' viewBox='0 0 56 100'%3E%3Cpath d='M28 66L0 50V18L28 2l28 16v32L28 66zm0 0v34' fill='none' stroke='%2322d3ee' stroke-width='0.5'/%3E%3C/svg%3E")`,
        backgroundSize: "56px 100px",
      }} />

      {/* Ambient glows */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[700px] h-[700px] rounded-full blur-[140px]"
             style={{ background: "radial-gradient(circle,rgba(34,211,238,0.06),rgba(99,102,241,0.04),transparent 70%)" }} />
        <div className="absolute top-1/4 right-1/3 w-72 h-72 bg-blue-600/5 rounded-full blur-[80px]" />
      </div>

      {/* Scanline */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        <div className="absolute left-0 right-0 h-px" style={{
          background: "linear-gradient(90deg,transparent,rgba(34,211,238,0.35) 50%,transparent)",
          animation: "scanline 10s ease-in-out infinite",
        }} />
      </div>

      {/* Top / bottom bars */}
      <div className="absolute top-0 inset-x-0 h-px" style={{ background: "linear-gradient(90deg,transparent,rgba(34,211,238,0.6) 50%,transparent)" }} />
      <div className="absolute bottom-0 inset-x-0 h-px" style={{ background: "linear-gradient(90deg,transparent,rgba(99,102,241,0.4) 50%,transparent)" }} />

      {/* HUD corners */}
      {[
        "absolute top-5 left-5 border-l-2 border-t-2",
        "absolute top-5 right-5 border-r-2 border-t-2",
        "absolute bottom-5 left-5 border-l-2 border-b-2",
        "absolute bottom-5 right-5 border-r-2 border-b-2",
      ].map((cls, i) => (
        <div key={i} className={`${cls} w-8 h-8 border-cyan-400/30 pointer-events-none`}
             style={{ animation: `corner-appear 0.8s ease both ${300 + i * 80}ms` }} />
      ))}

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
            <div className="hidden lg:flex flex-col justify-between p-8 border-r border-white/[0.04] bg-gradient-to-b from-gray-900/50 to-gray-950/30">
              {/* Logo */}
              <div>
                <div className="relative inline-flex items-center justify-center w-20 h-20 mb-6">
                  <div className="absolute inset-0 border border-cyan-500/25 rounded-full" style={{ animation: "spin-slow 12s linear infinite" }} />
                  <div className="absolute inset-1.5 border border-indigo-400/20 rounded-full" style={{ animation: "spin-slow 8s linear infinite reverse" }} />
                  <span className="absolute inset-0 rounded-full" style={{ boxShadow: "0 0 0 1px rgba(34,211,238,0.15)", animation: "pulse-ring 2.4s ease-out infinite" }} />
                  <div className="relative w-14 h-14 rounded-2xl bg-gray-900 border border-cyan-500/40 flex items-center justify-center"
                       style={{ boxShadow: "0 0 28px rgba(34,211,238,0.2),inset 0 0 16px rgba(34,211,238,0.06)" }}>
                    <BrainCircuit size={28} className="text-cyan-400" />
                  </div>
                </div>

                <div className="text-[9px] font-mono font-bold tracking-[0.28em] text-cyan-400/50 uppercase mb-2">
                  COMAC · 商用飞机有限责任公司
                </div>
                <h1 className="text-2xl font-bold mb-1 leading-tight" style={{
                  backgroundImage: "linear-gradient(135deg,#e2e8f0 0%,#38bdf8 45%,#818cf8 100%)",
                  backgroundClip: "text", WebkitBackgroundClip: "text", color: "transparent",
                  backgroundSize: "200% 200%", animation: "gradient-sweep 5s ease infinite",
                }}>
                  航空工艺<br />知识库系统
                </h1>
                <p className="text-xs text-gray-600 mb-8">CPS GraphRAG 规范智能检索与问答平台</p>

                {/* Feature list */}
                <div className="space-y-3">
                  {FEATURES.map(({ Icon, text }, i) => (
                    <div key={i} className="flex items-center gap-3 group"
                         style={{ animation: `slide-in-left 0.45s ease both ${400 + i * 80}ms` }}>
                      <div className="w-7 h-7 rounded-lg bg-cyan-500/8 border border-cyan-500/15 flex items-center justify-center flex-shrink-0
                                      group-hover:border-cyan-500/35 group-hover:bg-cyan-500/12 transition-all">
                        <Icon size={13} className="text-cyan-400/60 group-hover:text-cyan-400 transition-colors" />
                      </div>
                      <span className="text-xs text-gray-500 group-hover:text-gray-300 transition-colors">{text}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Bottom telemetry */}
              <div className="mt-8 pt-5 border-t border-white/[0.04]">
                <div className="grid grid-cols-2 gap-2 mb-3">
                  {[
                    { label: "API_STATUS",  val: "ONLINE",   color: "#4ade80" },
                    { label: "ENCRYPT",     val: "TLS_1.3",  color: "#22d3ee" },
                    { label: "AUTH_MODE",   val: "JWT_RS256",color: "#60a5fa" },
                    { label: "SYS_CLK",     val: tick,       color: "#a78bfa" },
                  ].map(({ label, val, color }) => (
                    <div key={label} className="rounded-lg bg-gray-900/60 border border-gray-800/60 px-2.5 py-2">
                      <div className="text-[7px] font-mono text-gray-700 mb-0.5">{label}</div>
                      <div className="text-[10px] font-mono font-bold tabular-nums" style={{ color }}>{val}</div>
                    </div>
                  ))}
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" style={{ boxShadow: "0 0 6px #4ade80" }} />
                  <span className="text-[9px] font-mono text-gray-600">ALL SYSTEMS NOMINAL</span>
                </div>
              </div>
            </div>

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
              <div className="flex items-center gap-2 mb-6">
                <Shield size={12} className="text-cyan-400/60" />
                <span className="text-[10px] font-mono text-gray-600 tracking-[0.2em] uppercase">身份验证</span>
                <div className="flex-1 h-px bg-gradient-to-r from-gray-700/60 to-transparent" />
                <span className="text-[9px] font-mono text-gray-700">ACCESS_CTRL</span>
              </div>

              {/* Forgot panel */}
              {showForgot && (
                <div className="mb-5 bg-amber-950/30 border border-amber-700/25 rounded-xl p-4 relative"
                     style={{ animation: "scale-fade 0.2s ease both" }}>
                  <button onClick={() => setShowForgot(false)}
                    className="absolute top-3 right-3 text-gray-600 hover:text-gray-300 transition-colors">
                    <X size={13} />
                  </button>
                  <div className="text-xs font-semibold text-amber-300 mb-2 font-mono">[ 密码重置流程 ]</div>
                  <div className="text-[11px] text-gray-500 space-y-1 font-mono">
                    <div>01 · 联系管理员，提供 6 位工号</div>
                    <div>02 · 管理员在后台执行重置操作</div>
                    <div>03 · 登录后立即前往「设置」修改密码</div>
                  </div>
                </div>
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
                  <label className="text-[10px] font-mono text-gray-600 mb-1.5 block tracking-widest">EMPLOYEE_ID</label>
                  <input
                    value={form.username}
                    onChange={e => setForm(f => ({ ...f, username: e.target.value }))}
                    placeholder="输入 6 位工号"
                    maxLength={6}
                    className="w-full px-3 py-3 bg-gray-900/70 border border-gray-700/60 rounded-xl text-sm text-gray-200 outline-none placeholder-gray-700 transition-all font-mono focus:border-cyan-500/60 focus:bg-gray-900 focus:shadow-[0_0_16px_rgba(34,211,238,0.08)]"
                  />
                </div>

                {/* Password */}
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <label className="text-[10px] font-mono text-gray-600 tracking-widest">ACCESS_CODE</label>
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
                  <span className="text-[10px] font-mono text-gray-600 group-hover:text-gray-400 transition-colors">REMEMBER_ID</span>
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

              <p className="text-center text-[10px] font-mono text-gray-700 mt-6 leading-relaxed">
                新用户账号由系统管理员统一创建<br />
                <span className="text-gray-800">ACCESS REQUEST → ADMIN → USER_MGMT</span>
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
