"use client";

import { AlertTriangle } from "lucide-react";
import type { LLMErrorInfo } from "./types";

const ERROR_HINTS: Record<string, string> = {
  quota_exceeded: "· 联系管理员充值或切换模型",
  rate_limited: "· 稍等片刻后重试",
  timeout: "· 点击重试，或换用响应更快的模型",
  service_unavailable: "· 检查 AI 服务是否正常运行",
  unknown_error: "· 联系管理员查看后端日志",
};

const ERROR_TITLES: Record<string, string> = {
  quota_exceeded: "API 额度不足",
  rate_limited: "请求过于频繁",
  timeout: "模型响应超时",
  service_unavailable: "AI 服务暂时不可用",
};

interface Props {
  errorInfo: LLMErrorInfo;
  isAdmin?: boolean;
  onRetry?: () => void;
}

export function MessageError({ errorInfo, isAdmin, onRetry }: Props) {
  const title = ERROR_TITLES[errorInfo.code] ?? "AI 服务异常";

  return (
    <div className="px-4 py-3 bg-amber-950/40 border border-amber-600/70 rounded-2xl rounded-tl-sm">
      <div className="flex items-start gap-2 mb-2">
        <AlertTriangle size={15} className="text-amber-400 mt-0.5 shrink-0" />
        <span className="text-sm font-medium text-amber-300">{title}</span>
      </div>
      <p className="text-xs text-amber-200/80 mb-3">{errorInfo.message}</p>

      {isAdmin && (errorInfo.status_code || errorInfo.endpoint) && (
        <div className="mb-3 px-3 py-2 bg-amber-900/30 border border-amber-700/40 rounded-lg text-xs text-amber-300/70 space-y-1">
          <div className="font-medium text-amber-400 mb-1">管理员信息</div>
          {errorInfo.status_code && (
            <div>HTTP 状态码：<span className="font-mono">{errorInfo.status_code}</span></div>
          )}
          {errorInfo.endpoint && (
            <div>端点：<span className="font-mono break-all">{errorInfo.endpoint}</span></div>
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

      <div className="text-xs text-amber-400/60 space-y-0.5">
        <div className="font-medium mb-1">你可以：</div>
        <div>{ERROR_HINTS[errorInfo.code] ?? ERROR_HINTS.unknown_error}</div>
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="mt-2 px-3 py-1 text-xs bg-amber-800/40 hover:bg-amber-700/50
                       border border-amber-600/50 rounded-lg text-amber-300 transition-colors"
          >
            重试
          </button>
        )}
      </div>
    </div>
  );
}
