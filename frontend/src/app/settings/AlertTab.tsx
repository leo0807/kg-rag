"use client";

import { useState } from "react";
import { fetchApi } from "@/lib/api";
import { getToken } from "./types";

interface Props {
  showMsg:   (m: string) => void;
  showError: (e: string) => void;
}

export function AlertTab({ showMsg, showError }: Props) {
  const [dingtalk,  setDingtalk]  = useState("");
  const [wecom,     setWecom]     = useState("");
  const [cooldown,  setCooldown]  = useState("30");
  const [testing,   setTesting]   = useState(false);
  const [saving,    setSaving]    = useState(false);

  async function handleSave() {
    setSaving(true);
    try {
      await fetchApi("/api/settings/system", {
        method: "PUT",
        headers: { Authorization: `Bearer ${getToken()}`, "Content-Type": "application/json" },
        body: JSON.stringify({
          settings: {
            DINGTALK_WEBHOOK:       dingtalk,
            WECOM_WEBHOOK:          wecom,
            ALERT_COOLDOWN_MINUTES: cooldown,
          },
        }),
      });
      showMsg("告警配置已保存");
    } catch (e) {
      showError(String(e));
    } finally {
      setSaving(false);
    }
  }

  async function handleTest() {
    if (!dingtalk && !wecom) {
      showError("请先填写至少一个 Webhook URL");
      return;
    }
    setTesting(true);
    try {
      await fetchApi("/api/settings/alert/test", {
        method: "POST",
        headers: { Authorization: `Bearer ${getToken()}`, "Content-Type": "application/json" },
        body: JSON.stringify({ dingtalk_webhook: dingtalk, wecom_webhook: wecom }),
      });
      showMsg("测试消息已发送，请检查对应群聊");
    } catch (e) {
      showError(String(e));
    } finally {
      setTesting(false);
    }
  }

  return (
    <div className="space-y-5">
      <div className="bg-gray-950 border border-gray-800 rounded-xl p-5 space-y-4">
        <h3 className="text-sm font-semibold text-white">Webhook 配置</h3>

        <div className="space-y-3">
          <label className="block">
            <span className="text-xs text-gray-400">钉钉机器人 Webhook</span>
            <input
              value={dingtalk}
              onChange={(e) => setDingtalk(e.target.value)}
              placeholder="https://oapi.dingtalk.com/robot/send?access_token=..."
              className="mt-1 w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg
                         text-sm text-gray-200 outline-none focus:border-indigo-500 placeholder-gray-600"
            />
          </label>

          <label className="block">
            <span className="text-xs text-gray-400">企业微信机器人 Webhook</span>
            <input
              value={wecom}
              onChange={(e) => setWecom(e.target.value)}
              placeholder="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=..."
              className="mt-1 w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg
                         text-sm text-gray-200 outline-none focus:border-indigo-500 placeholder-gray-600"
            />
          </label>

          <label className="block">
            <span className="text-xs text-gray-400">告警冷却时间（分钟）</span>
            <input
              type="number"
              min={1}
              max={1440}
              value={cooldown}
              onChange={(e) => setCooldown(e.target.value)}
              className="mt-1 w-32 px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg
                         text-sm text-gray-200 outline-none focus:border-indigo-500"
            />
            <p className="mt-1 text-xs text-gray-600">同一告警标题在冷却期内只推送一次</p>
          </label>
        </div>
      </div>

      <div className="bg-gray-950 border border-gray-800 rounded-xl p-5">
        <h3 className="text-sm font-semibold text-white mb-3">触发场景</h3>
        <ul className="space-y-1.5 text-xs text-gray-400">
          <li>🔴 文档批量解析失败（失败数 &gt; 5）</li>
          <li>⚠️ Neo4j / Milvus / ES 服务不可用</li>
          <li>⚠️ 检索平均延迟超过 5000ms</li>
          <li>⚠️ MinIO 存储使用率超过 85%</li>
          <li>🔴 LLM 服务不可用（API Key 失效等）</li>
        </ul>
      </div>

      <div className="flex gap-3">
        <button
          type="button"
          onClick={handleTest}
          disabled={testing}
          className="px-4 py-2 rounded-lg border border-gray-700 text-sm text-gray-300
                     hover:border-indigo-500 hover:text-white transition-colors disabled:opacity-50"
        >
          {testing ? "发送中…" : "测试发送"}
        </button>
        <button
          type="button"
          onClick={handleSave}
          disabled={saving}
          className="px-4 py-2 rounded-lg bg-indigo-600 text-sm text-white
                     hover:bg-indigo-500 transition-colors disabled:opacity-50"
        >
          {saving ? "保存中…" : "保存配置"}
        </button>
      </div>
    </div>
  );
}
