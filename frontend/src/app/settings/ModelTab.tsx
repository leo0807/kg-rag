"use client";

import { useEffect, useState } from "react";

import { fetchApi } from "@/lib/api";

import type { ModelSettings } from "./types";

interface Props {
  showMsg: (m: string) => void;
  showError: (e: string) => void;
}

interface Field {
  key: keyof ModelSettings;
  label: string;
  placeholder?: string;
  type?: "text" | "password";
}

function SectionCard({
  title,
  desc,
  children,
}: {
  title: string;
  desc: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-gray-800 bg-gray-950/90 p-4 sm:p-5">
      <div className="mb-4">
        <div className="text-sm font-semibold text-white">{title}</div>
        <div className="mt-1 text-xs leading-5 text-gray-500">{desc}</div>
      </div>
      {children}
    </section>
  );
}

function ModeSwitch({
  value,
  options,
  onChange,
}: {
  value: string;
  options: { label: string; value: string }[];
  onChange: (value: string) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {options.map((option) => (
        <button
          type="button"
          key={option.value}
          onClick={() => onChange(option.value)}
          className={`rounded-full border px-3 py-1.5 text-xs transition-colors ${
            value === option.value
              ? "border-amber-400/70 bg-amber-500/15 text-white"
              : "border-gray-700 text-gray-400 hover:border-gray-500 hover:text-white"
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

function FieldGrid({
  settings,
  fields,
  onChange,
}: {
  settings: ModelSettings;
  fields: Field[];
  onChange: (key: keyof ModelSettings, value: string) => void;
}) {
  return (
    <div className="grid gap-3 md:grid-cols-2">
      {fields.map((field) => (
        <div key={field.key}>
          <label
            htmlFor={String(field.key)}
            className="mb-1 block text-xs text-gray-500"
          >
            {field.label}
          </label>
          <input
            id={String(field.key)}
            type={field.type ?? "text"}
            value={settings[field.key]}
            onChange={(event) => onChange(field.key, event.target.value)}
            placeholder={field.placeholder}
            className="w-full rounded-xl border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-gray-100 outline-none transition-colors focus:border-amber-400/70"
          />
        </div>
      ))}
    </div>
  );
}

export function ModelTab({ showMsg, showError }: Props) {
  const [settings, setSettings] = useState<ModelSettings | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchApi<ModelSettings>("/api/settings/user")
      .then(setSettings)
      .catch((error: Error) => showError(error.message));
  }, [showError]);

  function update(key: keyof ModelSettings, value: string) {
    setSettings((current) =>
      current ? { ...current, [key]: value } : current,
    );
  }

  async function save() {
    if (!settings) return;
    setSaving(true);
    try {
      await fetchApi("/api/settings/user", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ settings }),
      });
      showMsg("模型设置已保存，新的问答请求会按当前账号配置生效");
    } catch (error) {
      showError(error instanceof Error ? error.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }

  if (!settings) return <div className="text-sm text-gray-500">加载中…</div>;

  const llmApiFields: Field[] =
    settings.llm_provider === "ernie"
      ? [
          {
            key: "llm_api_key",
            label: "API Key",
            placeholder: "百度 API Key",
            type: "password",
          },
          {
            key: "llm_api_secret",
            label: "Secret Key",
            placeholder: "百度 Secret Key",
            type: "password",
          },
          { key: "llm_model", label: "模型名称", placeholder: "ernie-4.5-8k" },
        ]
      : settings.llm_provider === "anthropic"
        ? [
            {
              key: "llm_api_key",
              label: "API Key",
              placeholder: "sk-ant-...",
              type: "password",
            },
            {
              key: "llm_model",
              label: "模型名称",
              placeholder: "claude-3-5-sonnet-latest",
            },
          ]
        : settings.llm_provider === "qwen"
          ? [
              {
                key: "llm_api_key",
                label: "API Key",
                placeholder: "DashScope Key",
                type: "password",
              },
              { key: "llm_model", label: "模型名称", placeholder: "qwen-plus" },
            ]
          : settings.llm_provider === "deepseek"
            ? [
                {
                  key: "llm_api_key",
                  label: "API Key",
                  placeholder: "DeepSeek Key",
                  type: "password",
                },
                {
                  key: "llm_model",
                  label: "模型名称",
                  placeholder: "deepseek-chat",
                },
              ]
            : [
                {
                  key: "llm_api_url",
                  label: "API 地址",
                  placeholder: "https://api.openai.com/v1",
                },
                {
                  key: "llm_api_key",
                  label: "API Key",
                  placeholder: "sk-...",
                  type: "password",
                },
                {
                  key: "llm_model",
                  label: "模型名称",
                  placeholder: "gpt-4.1-mini / qwen-plus / 自定义模型名",
                },
              ];

  return (
    <div className="space-y-4 sm:space-y-6">
      <SectionCard
        title="语言模型（LLM）"
        desc="控制问答、追问建议、多跳解释等文本生成能力。API 模式默认兼容 OpenAI 风格的 /chat/completions 接口；本地模式走 Ollama。"
      >
        <div className="space-y-4">
          <ModeSwitch
            value={settings.llm_mode}
            options={[
              { value: "api", label: "API 模式" },
              { value: "local", label: "本地模型" },
            ]}
            onChange={(value) => update("llm_mode", value)}
          />
          <div>
            <label
              htmlFor="llm-provider"
              className="mb-1 block text-xs text-gray-500"
            >
              提供方
            </label>
            <select
              id="llm-provider"
              value={settings.llm_provider}
              onChange={(event) => update("llm_provider", event.target.value)}
              className="w-full rounded-xl border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-gray-100 outline-none focus:border-amber-400/70"
            >
              <option value="">OpenAI 兼容 / 自定义 API</option>
              <option value="qwen">通义千问</option>
              <option value="deepseek">DeepSeek</option>
              <option value="anthropic">Anthropic</option>
              <option value="ernie">文心一言</option>
            </select>
          </div>
          {settings.llm_mode === "local" ? (
            <FieldGrid
              settings={settings}
              onChange={update}
              fields={[
                {
                  key: "llm_model",
                  label: "本地模型名称",
                  placeholder: "qwen2.5:7b",
                },
              ]}
            />
          ) : (
            <FieldGrid
              settings={settings}
              onChange={update}
              fields={llmApiFields}
            />
          )}
        </div>
      </SectionCard>

      <SectionCard
        title="向量模型（Embedding）"
        desc="控制文本向量生成。API 模式默认兼容 OpenAI 风格的 /embeddings 接口；通义向量模式只需填 API Key 与模型名。"
      >
        <div className="space-y-4">
          <ModeSwitch
            value={settings.embedding_mode}
            options={[
              { value: "local", label: "本地模型" },
              { value: "api", label: "API 模式" },
            ]}
            onChange={(value) => update("embedding_mode", value)}
          />
          <div>
            <label
              htmlFor="embedding-provider"
              className="mb-1 block text-xs text-gray-500"
            >
              提供方
            </label>
            <select
              id="embedding-provider"
              value={settings.embedding_provider}
              onChange={(event) =>
                update("embedding_provider", event.target.value)
              }
              className="w-full rounded-xl border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-gray-100 outline-none focus:border-amber-400/70"
            >
              <option value="">OpenAI 兼容 / 自定义 API</option>
              <option value="qwen">通义向量</option>
            </select>
          </div>
          {settings.embedding_mode === "local" ? (
            <FieldGrid
              settings={settings}
              onChange={update}
              fields={[
                {
                  key: "embedding_model",
                  label: "模型路径",
                  placeholder: "models/bge-m3",
                },
              ]}
            />
          ) : (
            <FieldGrid
              settings={settings}
              onChange={update}
              fields={
                settings.embedding_provider === "qwen"
                  ? [
                      {
                        key: "embedding_api_key",
                        label: "API Key",
                        placeholder: "DashScope Key",
                        type: "password",
                      },
                      {
                        key: "embedding_model",
                        label: "模型名称",
                        placeholder: "text-embedding-v3",
                      },
                    ]
                  : [
                      {
                        key: "embedding_api_url",
                        label: "API 地址",
                        placeholder: "https://api.openai.com/v1",
                      },
                      {
                        key: "embedding_api_key",
                        label: "API Key",
                        placeholder: "sk-...",
                        type: "password",
                      },
                      {
                        key: "embedding_model",
                        label: "模型名称",
                        placeholder: "text-embedding-3-small",
                      },
                    ]
              }
            />
          )}
        </div>
      </SectionCard>

      <SectionCard
        title="重排模型（Reranker）"
        desc="控制检索结果精排。API 模式要求目标服务提供 POST /rerank，Body 至少支持 model、query、documents 三个字段。"
      >
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-4">
            <ModeSwitch
              value={settings.reranker_mode}
              options={[
                { value: "local", label: "本地模型" },
                { value: "api", label: "API 模式" },
              ]}
              onChange={(value) => update("reranker_mode", value)}
            />
            <ModeSwitch
              value={settings.reranker_enabled}
              options={[
                { value: "true", label: "启用精排" },
                { value: "false", label: "关闭精排" },
              ]}
              onChange={(value) => update("reranker_enabled", value)}
            />
          </div>
          {settings.reranker_mode === "local" ? (
            <FieldGrid
              settings={settings}
              onChange={update}
              fields={[
                {
                  key: "reranker_model",
                  label: "模型路径",
                  placeholder: "models/bge-reranker-v2-m3",
                },
              ]}
            />
          ) : (
            <FieldGrid
              settings={settings}
              onChange={update}
              fields={[
                {
                  key: "reranker_api_url",
                  label: "API 地址",
                  placeholder: "https://your-service.example.com",
                },
                {
                  key: "reranker_api_key",
                  label: "API Key",
                  placeholder: "token / sk-...",
                  type: "password",
                },
                {
                  key: "reranker_model",
                  label: "模型名称",
                  placeholder: "bge-reranker-v2-m3",
                },
              ]}
            />
          )}
        </div>
      </SectionCard>

      <SectionCard
        title="多模态与默认检索"
        desc="VLM 模型会影响图片问答与多模态分析；默认检索策略和 top_k 会作为账号级默认参数保存。"
      >
        <div className="grid gap-4 lg:grid-cols-2">
          <FieldGrid
            settings={settings}
            onChange={update}
            fields={[
              {
                key: "vlm_model",
                label: "VLM 模型名称",
                placeholder: "Qwen/Qwen2.5-VL-32B-Instruct",
              },
              {
                key: "qwen_vl_model",
                label: "Vision API 模型",
                placeholder: "qwen-vl-max",
              },
            ]}
          />
          <div className="space-y-4">
            <div>
              <div className="mb-2 block text-xs text-gray-500">
                视觉服务模式
              </div>
              <ModeSwitch
                value={settings.vision_mode}
                options={[
                  { value: "api", label: "API 模式" },
                  { value: "local", label: "本地模式" },
                ]}
                onChange={(value) => update("vision_mode", value)}
              />
            </div>
            <div>
              <div className="mb-2 block text-xs text-gray-500">
                默认检索策略
              </div>
              <div className="flex flex-wrap gap-2">
                {["parallel", "sequential", "graph_augmented", "multi_hop"].map(
                  (strategy) => (
                    <button
                      type="button"
                      key={strategy}
                      onClick={() => update("query_strategy", strategy)}
                      className={`rounded-full border px-3 py-1.5 text-xs transition-colors ${
                        settings.query_strategy === strategy
                          ? "border-amber-400/70 bg-amber-500/15 text-white"
                          : "border-gray-700 text-gray-400 hover:border-gray-500 hover:text-white"
                      }`}
                    >
                      {strategy}
                    </button>
                  ),
                )}
              </div>
            </div>
            <div>
              <div className="mb-2 block text-xs text-gray-500">
                默认返回章节数：{settings.query_top_k}
              </div>
              <input
                type="range"
                min="3"
                max="10"
                value={settings.query_top_k}
                onChange={(event) => update("query_top_k", event.target.value)}
                className="w-full accent-amber-500"
              />
            </div>
          </div>
        </div>
      </SectionCard>

      <div className="rounded-2xl border border-amber-500/20 bg-amber-500/5 p-4 text-xs leading-6 text-amber-100/85">
        <div className="font-semibold text-amber-200">API 接入标准</div>
        <div>LLM：需要兼容 OpenAI 风格的 `/chat/completions`。</div>
        <div>Embedding：需要兼容 `/embeddings`，返回 `data[].embedding`。</div>
        <div>
          Reranker：需要兼容 `/rerank`，返回 `results[].index + relevance_score`
          或 `data[].index + score`。
        </div>
      </div>

      <button
        type="button"
        onClick={save}
        disabled={saving}
        className="rounded-xl bg-amber-500 px-5 py-2 text-sm font-medium text-black transition-colors hover:bg-amber-400 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {saving ? "保存中..." : "保存模型设置"}
      </button>
    </div>
  );
}
