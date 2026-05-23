"use client";

import { AlertTriangle } from "lucide-react";
import type { LLMErrorInfo } from "./types";

const ERROR_HINTS: Record<string, string> = {
  auth_failed: "· 检查 API key 是否有效，或联系管理员更新配置",
  model_unavailable: "· 联系管理员检查 LLM_MODEL 配置或更换可用模型",
  quota_exceeded: "· 联系管理员充值或切换模型",
  forbidden: "· 联系管理员检查 API key 权限",
  rate_limited: "· 稍等片刻后重试",
  api_invalid_request: "· 联系管理员检查请求参数配置",
  timeout: "· 点击重试，或换用响应更快的模型",
  service_unavailable: "· 检查 AI 服务是否正常运行",
  stream_truncated: "· 已显示部分内容，可重新发送",
  stream_empty: "· 请稍后重试",
  network_error: "· 检查网络后重新发送",
  unknown_error: "· 联系管理员查看后端日志",
};

const ERROR_TITLES: Record<string, string> = {
  auth_failed: "API key 失效",
  model_unavailable: "LLM 模型不可用",
  quota_exceeded: "API 额度不足",
  forbidden: "LLM 服务拒绝访问",
  rate_limited: "调用频率超限",
  api_invalid_request: "LLM API 请求错误",
  timeout: "模型响应超时",
  service_unavailable: "AI 服务暂时不可用",
  stream_truncated: "回答中断",
  stream_empty: "服务暂时不可用",
  network_error: "网络连接异常",
};

function getTone(kind?: string) {
  if (kind === "network_error" || kind === "network" || kind === "auth_failed" || kind === "api_invalid_request") {
    return {
      container: "bg-red-950/40 border-red-600/70",
      icon: "text-red-400",
      title: "text-red-300",
      body: "text-red-200/80",
      footer: "text-red-400/60",
      hintButton:
        "bg-red-800/40 hover:bg-red-700/50 border-red-600/50 text-red-300",
    };
  }
  if (
    kind === "stream_truncated" ||
    kind === "stream_empty" ||
    kind === "interrupted"
  ) {
    return {
      container: "bg-slate-950/40 border-slate-600/70",
      icon: "text-slate-400",
      title: "text-slate-300",
      body: "text-slate-200/80",
      footer: "text-slate-400/60",
      hintButton:
        "bg-slate-800/40 hover:bg-slate-700/50 border-slate-600/50 text-slate-300",
    };
  }
  return {
    container: "bg-amber-950/40 border-amber-600/70",
    icon: "text-amber-400",
    title: "text-amber-300",
    body: "text-amber-200/80",
    footer: "text-amber-400/60",
    hintButton:
      "bg-amber-800/40 hover:bg-amber-700/50 border-amber-600/50 text-amber-300",
  };
}

interface Props {
  errorInfo: LLMErrorInfo;
  isAdmin?: boolean;
  onRetry?: () => void;
}

export function MessageError({ errorInfo, isAdmin, onRetry }: Props) {
  const tone = getTone((errorInfo as { kind?: string }).kind ?? errorInfo.code);
  const title = ERROR_TITLES[errorInfo.code] ?? "AI 服务异常";

  return (
    <div className={`px-4 py-3 border rounded-2xl rounded-tl-sm ${tone.container}`}>
      <div className="flex items-start gap-2 mb-2">
        <AlertTriangle size={15} className={`${tone.icon} mt-0.5 shrink-0`} />
        <span className={`text-sm font-medium ${tone.title}`}>{title}</span>
      </div>
      <p className={`text-xs mb-3 ${tone.body}`}>{errorInfo.message}</p>

      {isAdmin && (errorInfo.status_code || errorInfo.endpoint) && (
        <div className={`mb-3 px-3 py-2 border rounded-lg text-xs space-y-1 ${tone.container}`}>
          <div className={`font-medium mb-1 ${tone.title}`}>管理员信息</div>
          {errorInfo.status_code && (
            <div>
              HTTP 状态码：
              <span className="font-mono">{errorInfo.status_code}</span>
            </div>
          )}
          {errorInfo.endpoint && (
            <div>
              端点：
              <span className="font-mono break-all">{errorInfo.endpoint}</span>
            </div>
          )}
          {errorInfo.code === "quota_exceeded" && (
            <div className="mt-1 space-y-0.5">
              <div>建议操作：</div>
              <div>· 充值：检查 API 提供商控制台</div>
              <div>
                · 或在 <span className="font-mono">.env</span> 设置{" "}
                <span className="font-mono">LLM_MODE=local</span> 切换本地模型
              </div>
            </div>
          )}
        </div>
      )}

      <div className={`text-xs space-y-0.5 ${tone.footer}`}>
        <div className="font-medium mb-1">你可以：</div>
        <div>{ERROR_HINTS[errorInfo.code] ?? ERROR_HINTS.unknown_error}</div>
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className={`mt-2 px-3 py-1 text-xs border rounded-lg transition-colors ${tone.hintButton}`}
          >
            重新发送
          </button>
        )}
      </div>
    </div>
  );
}
