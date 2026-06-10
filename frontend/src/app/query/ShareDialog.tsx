"use client";

import { Copy, ExternalLink, Trash2, X } from "lucide-react";
import { useState } from "react";
import { fetchApi } from "@/lib/api";

interface Props {
  convId: string;
  onClose: () => void;
}

const EXPIRY_OPTIONS = [
  { label: "永不过期", value: null },
  { label: "7 天", value: 7 },
  { label: "30 天", value: 30 },
  { label: "90 天", value: 90 },
];

export function ShareDialog({ convId, onClose }: Props) {
  const [expiry, setExpiry] = useState<number | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  async function generate() {
    setLoading(true);
    try {
      const data = await fetchApi<{ token: string }>(
        `/api/conversations/${convId}/share`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ expires_days: expiry, is_public: true }),
        }
      );
      setToken(data.token);
    } finally {
      setLoading(false);
    }
  }

  async function revoke() {
    if (!confirm("撤销分享后，链接将立即失效，确认？")) return;
    await fetchApi(`/api/conversations/${convId}/share`, { method: "DELETE" });
    setToken(null);
  }

  function shareUrl() {
    return `${window.location.origin}/shared/${token}`;
  }

  function copy() {
    if (!token) return;
    navigator.clipboard.writeText(shareUrl());
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-gray-900 border border-gray-700 rounded-xl p-5 w-80 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-100">分享对话</h2>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-300"><X size={15} /></button>
        </div>

        {!token ? (
          <>
            <div className="space-y-2">
              <p className="text-xs text-gray-500">链接有效期</p>
              <div className="grid grid-cols-2 gap-1.5">
                {EXPIRY_OPTIONS.map((o) => (
                  <button key={String(o.value)} onClick={() => setExpiry(o.value)}
                    className={`px-3 py-1.5 text-xs rounded-lg border transition-colors ${
                      expiry === o.value
                        ? "border-indigo-600 bg-indigo-900/30 text-indigo-300"
                        : "border-gray-700 text-gray-400 hover:border-gray-600"
                    }`}>
                    {o.label}
                  </button>
                ))}
              </div>
            </div>
            <button onClick={generate} disabled={loading}
              className="w-full py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40
                         text-white text-xs rounded-lg transition-colors flex items-center justify-center gap-2">
              <ExternalLink size={12} />
              {loading ? "生成中…" : "生成分享链接"}
            </button>
          </>
        ) : (
          <div className="space-y-3">
            <div className="bg-gray-800 rounded-lg px-3 py-2 flex items-center gap-2">
              <span className="flex-1 text-[11px] text-gray-300 truncate">{shareUrl()}</span>
              <button onClick={copy}
                className={`shrink-0 text-xs px-2 py-1 rounded transition-colors ${
                  copied ? "text-green-400" : "text-gray-400 hover:text-white"
                }`}>
                {copied ? "已复制" : <Copy size={12} />}
              </button>
            </div>
            <div className="flex gap-2">
              <a href={shareUrl()} target="_blank" rel="noopener noreferrer"
                className="flex-1 flex items-center justify-center gap-1 py-1.5 border border-gray-700
                           text-xs text-gray-400 rounded-lg hover:text-white hover:border-gray-600">
                <ExternalLink size={11} /> 预览
              </a>
              <button onClick={revoke}
                className="flex items-center justify-center gap-1 px-3 py-1.5 border border-red-900
                           text-xs text-red-400 rounded-lg hover:bg-red-900/20 transition-colors">
                <Trash2 size={11} /> 撤销
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
