"use client";

import type { ModelSettings } from "./types";
import { FieldGrid, ModeSwitch, SectionCard } from "./ModelTabShared";

const SELECT = "w-full rounded-xl border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-gray-100 outline-none focus:border-amber-400/70";

interface Props { settings: ModelSettings; update: (key: keyof ModelSettings, value: string) => void }

export function EmbeddingSection({ settings, update }: Props) {
  const apiFields = settings.embedding_provider === "qwen"
    ? [
        { key: "embedding_api_key" as keyof ModelSettings, label: "API Key",  placeholder: "DashScope Key", type: "password" as const },
        { key: "embedding_model"   as keyof ModelSettings, label: "模型名称", placeholder: "text-embedding-v3" },
      ]
    : [
        { key: "embedding_api_url" as keyof ModelSettings, label: "API 地址", placeholder: "https://api.openai.com/v1" },
        { key: "embedding_api_key" as keyof ModelSettings, label: "API Key",  placeholder: "sk-...", type: "password" as const },
        { key: "embedding_model"   as keyof ModelSettings, label: "模型名称", placeholder: "text-embedding-3-small" },
      ];

  return (
    <SectionCard title="向量模型（Embedding）"
      desc="控制文本向量生成。API 模式默认兼容 OpenAI 风格的 /embeddings 接口；通义向量模式只需填 API Key 与模型名。">
      <div className="space-y-4">
        <ModeSwitch value={settings.embedding_mode}
          options={[{ value: "local", label: "本地模型" }, { value: "api", label: "API 模式" }]}
          onChange={(v) => update("embedding_mode", v)} />
        <div>
          <label htmlFor="embedding-provider" className="mb-1 block text-xs text-gray-500">提供方</label>
          <select id="embedding-provider" value={settings.embedding_provider}
            onChange={(e) => update("embedding_provider", e.target.value)} className={SELECT}>
            <option value="">OpenAI 兼容 / 自定义 API</option>
            <option value="qwen">通义向量</option>
          </select>
        </div>
        {settings.embedding_mode === "local"
          ? <FieldGrid settings={settings} onChange={update} fields={[{ key: "embedding_model", label: "模型路径", placeholder: "models/bge-m3" }]} />
          : <FieldGrid settings={settings} onChange={update} fields={apiFields} />}
      </div>
    </SectionCard>
  );
}
