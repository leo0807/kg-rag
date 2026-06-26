"use client";

import { GitBranch } from "lucide-react";
import { useState } from "react";
import { fetchApi } from "@/lib/api";

interface Props {
  conversationId: string;
  messageId: string;
  onBranch: (branchId: string) => void;
}

export function BranchButton({ conversationId, messageId, onBranch }: Props) {
  const [loading, setLoading] = useState(false);

  async function handleClick() {
    if (loading) return;
    setLoading(true);
    try {
      const res = await fetchApi<{ branch_id: string; title: string }>(
        `/api/conversations/${conversationId}/branch`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message_id: messageId }),
        },
      );
      if (res?.branch_id) {
        onBranch(res.branch_id);
      }
    } catch (e) {
      console.error("分支创建失败:", e);
    } finally {
      setLoading(false);
    }
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={loading}
      className="flex items-center gap-1 text-xs text-gray-500 transition-colors hover:text-indigo-400 disabled:opacity-50"
      title="从此消息分支出新对话"
    >
      <GitBranch size={12} />
      {loading ? "创建中…" : "⑂ 分支"}
    </button>
  );
}
