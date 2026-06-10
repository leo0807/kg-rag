"use client";
import { useEffect, useState } from "react";

type Notification = {
  id: string;
  type: string;        // answer.created / evaluation.completed / alert.triggered …
  title: string;
  body: string;
  is_read: boolean;
  created_at: string;
};

const TYPE_COLOR: Record<string, string> = {
  "answer.created":        "bg-blue-900 text-blue-300",
  "evaluation.completed":  "bg-green-900 text-green-300",
  "alert.triggered":       "bg-red-900 text-red-300",
  "quota.exceeded":        "bg-yellow-900 text-yellow-300",
  "document.uploaded":     "bg-purple-900 text-purple-300",
};

const MOCK: Notification[] = [
  { id: "1", type: "alert.triggered",  title: "CPU 使用率告警", body: "节点 gpu-01 CPU 超过 90%", is_read: false, created_at: new Date().toISOString() },
  { id: "2", type: "evaluation.completed", title: "评测完成", body: "数据集 CPS-v2 评测已完成，BLEU=0.82", is_read: false, created_at: new Date(Date.now()-3600_000).toISOString() },
  { id: "3", type: "document.uploaded", title: "文档上传成功", body: "CPS-规范-2026.pdf 已处理完毕", is_read: true, created_at: new Date(Date.now()-86400_000).toISOString() },
  { id: "4", type: "quota.exceeded", title: "配额告警", body: "本月查询次数已达上限的 80%", is_read: true, created_at: new Date(Date.now()-172800_000).toISOString() },
];

export default function NotificationsPage() {
  const [notifications, setNotifications] = useState<Notification[]>(MOCK);
  const [filter, setFilter] = useState<"all" | "unread">("all");

  const unreadCount = notifications.filter((n) => !n.is_read).length;
  const displayed   = filter === "unread"
    ? notifications.filter((n) => !n.is_read)
    : notifications;

  const markRead = (id: string) =>
    setNotifications((ns) => ns.map((n) => n.id === id ? { ...n, is_read: true } : n));

  const markAllRead = () =>
    setNotifications((ns) => ns.map((n) => ({ ...n, is_read: true })));

  const relativeTime = (iso: string) => {
    const diff = Date.now() - new Date(iso).getTime();
    if (diff < 60_000)    return "刚刚";
    if (diff < 3600_000)  return `${Math.floor(diff / 60_000)} 分钟前`;
    if (diff < 86400_000) return `${Math.floor(diff / 3600_000)} 小时前`;
    return `${Math.floor(diff / 86400_000)} 天前`;
  };

  return (
    <div className="p-6 max-w-3xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white">通知中心</h1>
          {unreadCount > 0 && (
            <p className="text-gray-400 text-sm mt-1">{unreadCount} 条未读</p>
          )}
        </div>
        <div className="flex items-center gap-3">
          <div className="flex rounded overflow-hidden border border-gray-700">
            {(["all", "unread"] as const).map((f) => (
              <button key={f} onClick={() => setFilter(f)}
                className={`px-3 py-1.5 text-xs ${filter === f ? "bg-blue-700 text-white" : "bg-gray-800 text-gray-400"}`}>
                {f === "all" ? "全部" : "未读"}
              </button>
            ))}
          </div>
          {unreadCount > 0 && (
            <button onClick={markAllRead} className="text-xs text-blue-400 hover:underline">
              全部标为已读
            </button>
          )}
        </div>
      </div>

      <div className="space-y-2">
        {displayed.length === 0 && (
          <div className="text-center text-gray-500 py-16 text-sm">暂无通知</div>
        )}
        {displayed.map((n) => (
          <div
            key={n.id}
            onClick={() => markRead(n.id)}
            className={`bg-gray-900 border rounded-lg p-4 cursor-pointer hover:bg-gray-800/60 transition-colors ${
              n.is_read ? "border-gray-800" : "border-blue-800"
            }`}
          >
            <div className="flex items-start gap-3">
              {!n.is_read && (
                <div className="w-2 h-2 rounded-full bg-blue-500 mt-1.5 shrink-0" />
              )}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className={`text-xs px-1.5 py-0.5 rounded ${TYPE_COLOR[n.type] ?? "bg-gray-700 text-gray-300"}`}>
                    {n.type}
                  </span>
                  <span className="text-gray-500 text-xs">{relativeTime(n.created_at)}</span>
                </div>
                <p className="text-white text-sm font-medium">{n.title}</p>
                <p className="text-gray-400 text-xs mt-0.5">{n.body}</p>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
