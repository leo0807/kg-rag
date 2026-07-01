"use client";

import { useEffect, useState } from "react";
import { fetchApi } from "@/lib/api";
import type { ModelSettings } from "./types";
import { FieldGrid, ModeSwitch, SectionCard } from "./ModelTabShared";
import { LLMSection }       from "./LLMSection";
import { EmbeddingSection } from "./EmbeddingSection";
import { RerankerSection }  from "./RerankerSection";

interface Props { showMsg: (m: string) => void; showError: (e: string) => void }

const STRATEGIES = ["parallel", "sequential", "graph_augmented", "multi_hop"];

export function ModelTab({ showMsg, showError }: Props) {
  const [settings, setSettings] = useState<ModelSettings | null>(null);
  const [saving,   setSaving]   = useState(false);

  useEffect(() => {
    fetchApi<ModelSettings>("/api/settings/user")
      .then(setSettings)
      .catch((e: Error) => showError(e.message));
  }, [showError]);

  function update(key: keyof ModelSettings, value: string) {
    setSettings(curr => curr ? { ...curr, [key]: value } : curr);
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
    } catch (e) {
      showError(e instanceof Error ? e.message : "保存失败");
    } finally { setSaving(false); }
  }

  if (!settings) return <div className="text-sm text-gray-500">加载中…</div>;

  return (
    <div className="space-y-4 sm:space-y-6">
      <LLMSection       settings={settings} update={update} />
      <EmbeddingSection settings={settings} update={update} />
      <RerankerSection  settings={settings} update={update} />

      <SectionCard title="多模态与默认检索"
        desc="VLM 模型会影响图片问答与多模态分析；默认检索策略和 top_k 会作为账号级默认参数保存。">
        <div className="grid gap-4 lg:grid-cols-2">
          <FieldGrid settings={settings} onChange={update} fields={[
            { key: "vlm_model",      label: "VLM 模型名称",  placeholder: "Qwen/Qwen2.5-VL-32B-Instruct" },
            { key: "qwen_vl_model",  label: "Vision API 模型",placeholder: "qwen-vl-max" },
          ]} />
          <div className="space-y-4">
            <div>
              <div className="mb-2 text-xs text-gray-500">视觉服务模式</div>
              <ModeSwitch value={settings.vision_mode}
                options={[{ value: "api", label: "API 模式" }, { value: "local", label: "本地模式" }]}
                onChange={(v) => update("vision_mode", v)} />
            </div>
            <div>
              <div className="mb-2 text-xs text-gray-500">默认检索策略</div>
              <div className="flex flex-wrap gap-2">
                {STRATEGIES.map(s => (
                  <button type="button" key={s} onClick={() => update("query_strategy", s)}
                    className={`rounded-full border px-3 py-1.5 text-xs transition-colors ${
                      settings.query_strategy === s
                        ? "border-amber-400/70 bg-amber-500/15 text-white"
                        : "border-gray-700 text-gray-400 hover:border-gray-500 hover:text-white"
                    }`}>{s}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <div className="mb-2 text-xs text-gray-500">默认返回章节数：{settings.query_top_k}</div>
              <input type="range" min="3" max="10" value={settings.query_top_k}
                onChange={(e) => update("query_top_k", e.target.value)}
                className="w-full accent-amber-500" />
            </div>
          </div>
        </div>
      </SectionCard>

      <div className="rounded-2xl border border-amber-500/20 bg-amber-500/5 p-4 text-xs leading-6 text-amber-100/85">
        <div className="font-semibold text-amber-200">API 接入标准</div>
        <div>LLM：需要兼容 OpenAI 风格的 `/chat/completions`。</div>
        <div>Embedding：需要兼容 `/embeddings`，返回 `data[].embedding`。</div>
        <div>Reranker：需要兼容 `/rerank`，返回 `results[].index + relevance_score` 或 `data[].index + score`。</div>
      </div>

      <button type="button" onClick={save} disabled={saving}
        className="rounded-xl bg-amber-500 px-5 py-2 text-sm font-medium text-black transition-colors hover:bg-amber-400 disabled:cursor-not-allowed disabled:opacity-60">
        {saving ? "保存中..." : "保存模型设置"}
      </button>
    </div>
  );
}
