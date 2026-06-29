"use client";

import { Eye, EyeOff, Shield, ChevronRight, BrainCircuit, Fingerprint, Lock } from "lucide-react";
import ForgotPanel, { type ForgotState } from "./ForgotPanel";

interface Props {
  loading: boolean;
  error: string;
  showPw: boolean;
  showForgot: boolean;
  rememberMe: boolean;
  form: { username: string; password: string };
  forgotState: ForgotState;
  forgotMsg: string;
  setShowPw: (v: boolean | ((p: boolean) => boolean)) => void;
  setShowForgot: (v: boolean | ((p: boolean) => boolean)) => void;
  setRememberMe: (v: boolean | ((p: boolean) => boolean)) => void;
  setForm: (fn: (f: { username: string; password: string }) => { username: string; password: string }) => void;
  setForgotState: (s: ForgotState) => void;
  setForgotMsg: (m: string) => void;
  handleForgot: () => void;
  handleLogin: () => void;
  sessionId: string;
}

const AUTH_STEPS = [
  { label: "连接加密",  done: true  },
  { label: "密钥交换",  done: true  },
  { label: "身份核验",  done: false },
  { label: "权限授予",  done: false },
];

export default function LoginFormPanel({
  loading, error, showPw, showForgot, rememberMe,
  form, forgotState, forgotMsg,
  setShowPw, setShowForgot, setRememberMe, setForm,
  setForgotState, setForgotMsg, handleForgot, handleLogin, sessionId,
}: Props) {
  return (
    <div className="relative p-8 flex flex-col justify-center overflow-hidden">
      {/* Subtle inner grid texture */}
      <div className="absolute inset-0 pointer-events-none opacity-[0.015]" style={{
        backgroundImage: "linear-gradient(rgba(34,211,238,0.8) 1px,transparent 1px),linear-gradient(90deg,rgba(34,211,238,0.8) 1px,transparent 1px)",
        backgroundSize: "32px 32px",
      }} />

      {/* Mobile logo */}
      <div className="lg:hidden text-center mb-6">
        <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-gray-900 border border-cyan-500/40 mb-3"
             style={{ boxShadow: "0 0 24px rgba(34,211,238,0.18)" }}>
          <BrainCircuit size={22} className="text-cyan-400" />
        </div>
        <h1 className="text-xl font-bold text-white">航空工艺知识库系统</h1>
      </div>

      {/* Section header */}
      <div className="flex items-center gap-2 mb-4">
        <Shield size={12} className="text-cyan-400/60" />
        <span className="text-[10px] font-mono text-gray-600 tracking-[0.2em] uppercase">身份验证</span>
        <div className="flex-1 h-px bg-gradient-to-r from-gray-700/60 to-transparent" />
        <span className="text-[9px] font-mono text-gray-700">访问控制</span>
      </div>

      {/* Auth sequence steps */}
      <div className="flex items-center gap-1.5 mb-4">
        {AUTH_STEPS.map((step, i) => (
          <div key={i} className="flex items-center gap-1">
            <div className={`w-1.5 h-1.5 rounded-full ${step.done ? "bg-emerald-400" : "bg-gray-700"} transition-colors`}
                 style={step.done ? { boxShadow: "0 0 4px #4ade80", animation: "pulse-ring 2.5s ease-out infinite" } : {}} />
            <span className={`text-[8px] font-mono ${step.done ? "text-emerald-600" : "text-gray-700"}`}>{step.label}</span>
            {i < AUTH_STEPS.length - 1 && (
              <div className={`w-4 h-px ${step.done ? "bg-emerald-800/60" : "bg-gray-800"} mx-0.5`} />
            )}
          </div>
        ))}
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

      {/* Forgot / Error panels */}
      {showForgot && (
        <ForgotPanel
          state={forgotState} msg={forgotMsg} username={form.username}
          onClose={() => { setShowForgot(false); setForgotState("idle"); setForgotMsg(""); }}
          onSubmit={handleForgot}
        />
      )}
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
            inputMode="numeric" placeholder="输入 6 位工号" maxLength={6}
            className="w-full px-3 py-3 bg-gray-900/70 border border-gray-700/60 rounded-xl text-sm text-gray-200 outline-none placeholder-gray-700 transition-all font-mono focus:border-cyan-500/60 focus:bg-gray-900 focus:shadow-[0_0_16px_rgba(34,211,238,0.08)]"
          />
          {form.username.length > 0 && form.username.length < 6 && (
            <p className="mt-1 text-[10px] font-mono text-amber-500/80">工号须为 6 位数字（已输入 {form.username.length} 位）</p>
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
          <div onClick={() => setRememberMe(v => !v)}>
            <div className={`w-4 h-4 rounded border transition-all flex items-center justify-center
              ${rememberMe ? "bg-cyan-600 border-cyan-500 shadow-[0_0_8px_rgba(34,211,238,0.35)]" : "bg-gray-800 border-gray-700 group-hover:border-gray-500"}`}>
              {rememberMe && <svg width="9" height="7" viewBox="0 0 9 7" fill="none"><path d="M1 3.5L3.5 6L8 1" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>}
            </div>
          </div>
          <span className="text-[10px] font-mono text-gray-600 group-hover:text-gray-400 transition-colors">记住工号</span>
        </label>

        {/* Submit */}
        <button onClick={handleLogin} disabled={loading || !form.username || !form.password}
          className="relative w-full py-3 text-white text-sm rounded-xl font-bold transition-all mt-2 overflow-hidden disabled:opacity-40 disabled:cursor-not-allowed hover:brightness-110 active:scale-[0.98] tracking-widest font-mono"
          style={{
            background: "linear-gradient(135deg,#0891b2 0%,#2563eb 50%,#6366f1 100%)",
            boxShadow: "0 0 24px rgba(34,211,238,0.2)",
            clipPath: "polygon(8px 0%,100% 0%,calc(100% - 8px) 100%,0% 100%)",
          }}>
          <span className="absolute inset-0 pointer-events-none"
            style={{ background: "linear-gradient(90deg,transparent,rgba(255,255,255,0.1) 50%,transparent)", backgroundSize: "200% 100%", animation: "shine 2.5s linear infinite" }} />
          <span className="absolute inset-x-0 h-[1px]"
            style={{ background: "linear-gradient(90deg,transparent,rgba(255,255,255,0.5),transparent)", animation: "scan-down 4s linear infinite" }} />
          {loading ? (
            <span className="flex items-center justify-center gap-2">
              <Fingerprint size={15} className="animate-pulse" />
              AUTHENTICATING...
            </span>
          ) : (
            <span className="flex items-center justify-center gap-2">
              <Lock size={12} className="opacity-70" />
              [ 进入系统 ] <ChevronRight size={14} />
            </span>
          )}
        </button>
      </div>

      {/* Footer */}
      <div className="mt-5 border-t pt-4 space-y-1.5" style={{ borderColor: "rgba(255,255,255,0.04)" }}>
        <div className="flex items-center justify-between">
          <span className="text-[8px] font-mono text-gray-800">SES-ID: {sessionId}</span>
          <span className="text-[8px] font-mono text-gray-800">0 ANOMALIES</span>
        </div>
        <p className="text-center text-[10px] font-mono text-gray-700">新用户账号由系统管理员统一创建</p>
        <p className="text-center text-[8px] font-mono text-gray-800 tracking-widest">
          ALL ACCESS LOGGED · AES-256-GCM · ZERO TRUST
        </p>
      </div>
    </div>
  );
}
