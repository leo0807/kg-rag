"use client";

import { useState, useEffect } from "react";
import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";
import { type ForgotState } from "./ForgotPanel";
import LoginFormPanel from "./LoginFormPanel";

const ParticleCanvas  = dynamic(() => import("@/components/home/ParticleCanvas"), { ssr: false });
const FloatingData    = dynamic(() => import("@/components/home/FloatingData"),   { ssr: false });
const LoginBackdrop   = dynamic(() => import("./LoginBackdrop"),                   { ssr: false });
const LoginHUD        = dynamic(() => import("./LoginHUD"),                        { ssr: false });
// Defer the heavy left panel (3 spinning rings + radar + setInterval) — fixed placeholder prevents layout shift
const LoginInfoPanel  = dynamic(() => import("./LoginInfoPanel"), {
  ssr: false,
  loading: () => <div className="hidden lg:block" style={{ width: 360, flexShrink: 0 }} />,
});

export default function LoginPage() {
  const router = useRouter();
  const [loading, setLoading]           = useState(false);
  const [error, setError]               = useState("");
  const [showPw, setShowPw]             = useState(false);
  const [showForgot, setShowForgot]     = useState(false);
  const [rememberMe, setRememberMe]     = useState(false);
  const [rememberPw, setRememberPw]     = useState(false);
  const [form, setForm]                 = useState({ username: "", password: "" });
  const [tick, setTick]                 = useState("");
  const [forgotState, setForgotState]   = useState<ForgotState>("idle");
  const [forgotMsg, setForgotMsg]       = useState("");
  const [sessionId, setSessionId]       = useState("··········");

  // Restore saved credentials on mount
  useEffect(() => {
    const u = localStorage.getItem("remembered_username");
    const p = localStorage.getItem("remembered_password");
    if (u) { setForm(f => ({ ...f, username: u })); setRememberMe(true); }
    if (p) { setForm(f => ({ ...f, password: p })); setRememberPw(true); }
  }, []);

  // Sync rememberMe to localStorage immediately (don't wait for login)
  function handleRememberMeChange(v: boolean) {
    setRememberMe(v);
    if (v) {
      if (form.username) localStorage.setItem("remembered_username", form.username);
    } else {
      localStorage.removeItem("remembered_username");
    }
  }

  function handleRememberPwChange(v: boolean) {
    setRememberPw(v);
    if (v) {
      if (form.password) localStorage.setItem("remembered_password", form.password);
    } else {
      localStorage.removeItem("remembered_password");
    }
  }

  useEffect(() => {
    setTick(new Date().toLocaleTimeString("en-GB"));
    const iv = setInterval(() => setTick(new Date().toLocaleTimeString("en-GB")), 1000);
    return () => clearInterval(iv);
  }, []);

  useEffect(() => {
    setSessionId(`${Date.now().toString(36).toUpperCase()}-${Math.random().toString(36).slice(2,6).toUpperCase()}`);
  }, []);

  async function handleForgot() {
    if (!form.username) { setForgotMsg("请先填写工号"); setForgotState("error"); return; }
    setForgotState("loading");
    try {
      const res = await fetch("/api/auth/forgot-password", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: form.username }),
      });
      const data = await res.json();
      if (res.status === 429) { setForgotState("rate_limited"); setForgotMsg(data.detail || "申请已提交"); }
      else if (!res.ok)       { setForgotState("error");        setForgotMsg(data.detail || "发送失败，请稍后重试"); }
      else                    { setForgotState("sent");          setForgotMsg(data.detail || "申请已发送"); }
    } catch { setForgotState("error"); setForgotMsg("网络错误，请重试"); }
  }

  async function handleLogin() {
    setLoading(true); setError("");
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: form.username, password: form.password }),
      });
      const data = await res.json();
      if (!res.ok) { setError(data.detail || "登录失败，请重试"); return; }
      if (rememberMe) localStorage.setItem("remembered_username", form.username);
      else            localStorage.removeItem("remembered_username");
      if (rememberPw) localStorage.setItem("remembered_password", form.password);
      else            localStorage.removeItem("remembered_password");
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
      <LoginHUD />

      <div className="relative z-10 w-full max-w-4xl mt-6" style={{ animation: "page-enter 0.5s ease both" }}>
        <div className="absolute -inset-4 rounded-3xl pointer-events-none"
             style={{ background: "radial-gradient(ellipse,rgba(34,211,238,0.06) 0%,rgba(99,102,241,0.04) 50%,transparent 70%)" }} />
        <div className="relative rounded-2xl p-[1px]" style={{
          background: "linear-gradient(135deg,rgba(34,211,238,0.5),rgba(99,102,241,0.3),rgba(34,211,238,0.2))",
          backgroundSize: "200% 200%", animation: "gradient-sweep 5s ease infinite",
          boxShadow: "0 0 60px rgba(34,211,238,0.1), 0 0 120px rgba(99,102,241,0.06)",
        }}>
          <div className="absolute inset-0 rounded-2xl overflow-hidden pointer-events-none z-20">
            <div className="absolute inset-x-0 h-[2px]" style={{
              background: "linear-gradient(90deg,transparent,rgba(34,211,238,0.5) 50%,transparent)",
              animation: "scan-down 5s linear infinite",
            }} />
          </div>
          <div className="relative bg-gray-950 rounded-[15px] overflow-hidden grid grid-cols-1 lg:grid-cols-[360px_1fr]">
            <LoginInfoPanel tick={tick} />
            <LoginFormPanel
              loading={loading} error={error} showPw={showPw} showForgot={showForgot}
              rememberMe={rememberMe} rememberPw={rememberPw} form={form}
              forgotState={forgotState} forgotMsg={forgotMsg}
              setShowPw={setShowPw} setShowForgot={setShowForgot}
              setRememberMe={handleRememberMeChange} setRememberPw={handleRememberPwChange}
              setForm={setForm} setForgotState={setForgotState} setForgotMsg={setForgotMsg}
              handleForgot={handleForgot} handleLogin={handleLogin}
              sessionId={sessionId}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
