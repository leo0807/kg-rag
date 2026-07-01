"use client";

import type { ModelSettings } from "./types";
import { FieldGrid, ModeSwitch, SectionCard, type Field } from "./ModelTabShared";

function getLLMApiFields(settings: ModelSettings): Field[] {
  if (settings.llm_provider === "ernie") return [
    { key: "llm_api_key",    label: "API Key",    placeholder: "百度 API Key",    type: "password" },
    { key: "llm_api_secret", label: "Secret Key", placeholder: "百度 Secret Key", type: "password" },
    { key: "llm_model",      label: "模型名称",   placeholder: "ernie-4.5-8k" },
  ];
  if (settings.llm_provider === "anthropic") return [
    { key: "llm_api_key", label: "API Key",  placeholder: "sk-ant-...",               type: "password" },
    { key: "llm_model",   label: "模型名称", placeholder: "claude-3-5-sonnet-latest" },
  ];
  if (settings.llm_provider === "qwen") return [
    { key: "llm_api_key", label: "API Key",  placeholder: "DashScope Key", type: "password" },
    { key: "llm_model",   label: "模型名称", placeholder: "qwen-plus" },
  ];
  if (settings.llm_provider === "deepseek") return [
    { key: "llm_api_key", label: "API Key",  placeholder: "DeepSeek Key", type: "password" },
    { key: "llm_model",   label: "模型名称", placeholder: "deepseek-chat" },
  ];
  return [
    { key: "llm_api_url", label: "API 地址", placeholder: "https://api.openai.com/v1" },
    { key: "llm_api_key", label: "API Key",  placeholder: "sk-...", type: "password" },
    { key: "llm_model",   label: "模型名称", placeholder: "gpt-4.1-mini / qwen-plus / 自定义模型名" },
  ];
}

const SELECT = "w-full rounded-xl border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-gray-100 outline-none focus:border-amber-400/70";

interface Props { settings: ModelSettings; update: (key: keyof ModelSettings, value: string) => void }

export function LLMSection({ settings, update }: Props) {
  return (
    <SectionCard title="语言模型（LLM）"
      desc="控制问答、追问建议、多跳解释等文本生成能力。API 模式默认兼容 OpenAI 风格的 /chat/completions 接口；本地模式走 Ollama。">
      <div className="space-y-4">
        <ModeSwitch value={settings.llm_mode}
          options={[{ value: "api", label: "API 模式" }, { value: "local", label: "本地模型" }]}
          onChange={(v) => update("llm_mode", v)} />
        <div>
          <label htmlFor="llm-provider" className="mb-1 block text-xs text-gray-500">提供方</label>
          <select id="llm-provider" value={settings.llm_provider}
            onChange={(e) => update("llm_provider", e.target.value)} className={SELECT}>
            <option value="">OpenAI 兼容 / 自定义 API</option>
            <option value="qwen">通义千问</option>
            <option value="deepseek">DeepSeek</option>
            <option value="anthropic">Anthropic</option>
            <option value="ernie">文心一言</option>
          </select>
        </div>
        {settings.llm_mode === "local"
          ? <FieldGrid settings={settings} onChange={update} fields={[{ key: "llm_model", label: "本地模型名称", placeholder: "qwen2.5:7b" }]} />
          : <FieldGrid settings={settings} onChange={update} fields={getLLMApiFields(settings)} />}
      </div>
    </SectionCard>
  );
}
