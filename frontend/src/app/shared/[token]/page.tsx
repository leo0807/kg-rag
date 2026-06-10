"use client";

import { use, useEffect, useState } from "react";
import { getApiBaseUrl } from "@/lib/api";
import { Eye, MessageSquare } from "lucide-react";

interface SharedData {
  title: string;
  messages: { role: string; content: string; timestamp?: number }[];
  created_at: string;
  view_count: number;
  expires_at: string | null;
}

interface Props { params: Promise<{ token: string }> }

export default function SharedConversationPage({ params }: Props) {
  const { token } = use(params);
  const [data, setData] = useState<SharedData | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch(`${getApiBaseUrl()}/api/shared/${token}`)
      .then((r) => {
        if (!r.ok) throw new Error(r.status === 410 ? "链接已过期" : "链接不存在");
        return r.json();
      })
      .then(setData)
      .catch((e) => setError(e.message));
  }, [token]);

  if (error) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-400 text-sm">{error}</p>
          <p className="text-gray-600 text-xs mt-2">请向分享者索取新链接</p>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <p className="text-gray-500 text-xs">加载中…</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-950 text-gray-200">
      {/* Header */}
      <div className="max-w-2xl mx-auto px-4 pt-10 pb-4">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-lg font-semibold text-gray-100">{data.title}</h1>
            <p className="text-xs text-gray-500 mt-1">
              {new Date(data.created_at).toLocaleDateString("zh-CN")}
              {data.expires_at && ` · 有效至 ${new Date(data.expires_at).toLocaleDateString("zh-CN")}`}
            </p>
          </div>
          <div className="flex items-center gap-1 text-xs text-gray-600 shrink-0">
            <Eye size={12} /> {data.view_count}
          </div>
        </div>
        <div className="mt-2 text-[11px] text-amber-700 bg-amber-900/20 border border-amber-900/40 rounded-lg px-3 py-1.5">
          此为只读分享视图，内容由分享者提供
        </div>
      </div>

      {/* Messages */}
      <div className="max-w-2xl mx-auto px-4 pb-16 space-y-4">
        {data.messages.map((msg, i) => (
          <div key={i}
            className={`rounded-xl px-4 py-3 ${
              msg.role === "user"
                ? "bg-indigo-900/20 border border-indigo-900/40 ml-8"
                : "bg-gray-900 border border-gray-800"
            }`}>
            <div className="flex items-center gap-2 mb-2">
              <MessageSquare size={12} className={msg.role === "user" ? "text-indigo-400" : "text-gray-500"} />
              <span className="text-[10px] text-gray-500">
                {msg.role === "user" ? "用户" : "AI 助手"}
              </span>
            </div>
            <p className="text-sm text-gray-300 leading-relaxed whitespace-pre-wrap">{msg.content}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
