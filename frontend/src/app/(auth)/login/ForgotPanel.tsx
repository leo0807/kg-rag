"use client";

import { X } from "lucide-react";

export type ForgotState = "idle" | "loading" | "sent" | "rate_limited" | "error";

interface Props {
  state:     ForgotState;
  msg:       string;
  username:  string;
  onClose:   () => void;
  onSubmit:  () => void;
}

export default function ForgotPanel({ state, msg, username, onClose, onSubmit }: Props) {
  const bg = state === "sent"         ? "rgba(6,78,59,0.25)"
           : state === "rate_limited" ? "rgba(120,53,15,0.25)"
           :                            "rgba(30,58,138,0.18)";
  const border = state === "sent"         ? "rgba(52,211,153,0.3)"
               : state === "rate_limited" ? "rgba(251,191,36,0.3)"
               :                            "rgba(99,102,241,0.25)";

  return (
    <div className="mb-5 border rounded-xl p-4 relative"
         style={{ animation: "scale-fade 0.2s ease both", background: bg, borderColor: border }}>
      <button onClick={onClose}
        className="absolute top-3 right-3 text-gray-600 hover:text-gray-300 transition-colors">
        <X size={13} />
      </button>

      {state === "sent" ? (
        <>
          <div className="text-[11px] font-mono font-semibold text-emerald-400 mb-1">✓ 申请已发送</div>
          <div className="text-[11px] text-gray-400 font-mono">{msg}</div>
          <div className="text-[10px] text-gray-600 mt-2 font-mono">重置后请前往「设置」修改密码</div>
        </>
      ) : state === "rate_limited" ? (
        <>
          <div className="text-[11px] font-mono font-semibold text-amber-400 mb-1">⏳ 申请处理中</div>
          <div className="text-[11px] text-gray-400 font-mono">{msg}</div>
        </>
      ) : (
        <>
          <div className="text-[10px] font-mono text-indigo-300/80 mb-2">[ 密码重置申请 ]</div>
          <div className="text-[11px] text-gray-500 font-mono mb-3">
            系统将向管理员发送邮件提醒重置密码。<br />
            同一工号 24 小时内仅发送一次。
          </div>
          {state === "error" && msg && (
            <div className="text-[11px] text-red-400 font-mono mb-2">▲ {msg}</div>
          )}
          <div className="text-[10px] text-gray-600 font-mono mb-2">
            当前工号：{username || "（请先填写上方工号）"}
          </div>
          <button
            onClick={onSubmit}
            disabled={state === "loading" || !username}
            className="w-full py-2 rounded-lg text-[11px] font-mono font-semibold transition-all disabled:opacity-40"
            style={{ background: "rgba(99,102,241,0.25)", border: "1px solid rgba(99,102,241,0.4)", color: "#a5b4fc" }}>
            {state === "loading" ? (
              <span className="flex items-center justify-center gap-1.5">
                <span className="w-2.5 h-2.5 border border-indigo-400/30 border-t-indigo-400 rounded-full animate-spin" />
                发送中...
              </span>
            ) : "确认发送重置通知给管理员"}
          </button>
        </>
      )}
    </div>
  );
}
