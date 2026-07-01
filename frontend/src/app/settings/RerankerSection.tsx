"use client";

import type { ModelSettings } from "./types";
import { FieldGrid, ModeSwitch, SectionCard } from "./ModelTabShared";

interface Props { settings: ModelSettings; update: (key: keyof ModelSettings, value: string) => void }

export function RerankerSection({ settings, update }: Props) {
  const apiFields = [
    { key: "reranker_api_url" as keyof ModelSettings, label: "API 地址", placeholder: "https://your-service.example.com" },
    { key: "reranker_api_key" as keyof ModelSettings, label: "API Key",  placeholder: "token / sk-...", type: "password" as const },
    { key: "reranker_model"   as keyof ModelSettings, label: "模型名称", placeholder: "bge-reranker-v2-m3" },
  ];
  const localFields = [
    { key: "reranker_model" as keyof ModelSettings, label: "模型路径", placeholder: "models/bge-reranker-v2-m3" },
  ];

  return (
    <SectionCard title="重排模型（Reranker）"
      desc="控制检索结果精排。API 模式要求目标服务提供 POST /rerank，Body 至少支持 model、query、documents 三个字段。">
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-4">
          <ModeSwitch value={settings.reranker_mode}
            options={[{ value: "local", label: "本地模型" }, { value: "api", label: "API 模式" }]}
            onChange={(v) => update("reranker_mode", v)} />
          <ModeSwitch value={settings.reranker_enabled}
            options={[{ value: "true", label: "启用精排" }, { value: "false", label: "关闭精排" }]}
            onChange={(v) => update("reranker_enabled", v)} />
        </div>
        {settings.reranker_mode === "local"
          ? <FieldGrid settings={settings} onChange={update} fields={localFields} />
          : <FieldGrid settings={settings} onChange={update} fields={apiFields} />}
      </div>
    </SectionCard>
  );
}
