"use client";

import { useEffect, useState } from "react";
import { ApiError, fetchApi } from "@/lib/api";

export type PromptVersionInfo = {
  name: string;
  weight: number;
  max_tokens: number;
  temperature: number;
  model_preference: string;
};

export type PromptSummary = {
  id: string;
  description: string;
  active_version: string;
  model_preference: string;
  max_tokens: number;
  temperature: number;
  versions: PromptVersionInfo[];
  variables: string[];
  file: string;
};

export type PromptDetail = PromptSummary & {
  selected_version: string;
  template: {
    description?: string;
    model_preference?: string;
    max_tokens?: number;
    temperature?: number;
    system?: string;
    user?: string;
    variables?: string[];
    weight?: number;
    active_version?: string;
  };
};

export type PromptRender = {
  version: string;
  system: string;
  user: string;
  messages: { role: string; content: string }[];
  model: string;
  max_tokens: number;
  temperature: number;
};

export type PromptDraft = {
  description: string;
  model_preference: string;
  max_tokens: number;
  temperature: number;
  system: string;
  user: string;
  variables: string;
  weight: number;
};

const SAMPLE_VARIABLES = JSON.stringify(
  {
    sources:
      "【来源章节示例】\n[CPS1000 §6.2.23] 固化要求\n在燃油箱的承压侧...",
    question: "示例问题：通用密封的目的是________。",
    context:
      "【来源章节示例】\n[CPS1000 §6.2.23] 固化要求\n在燃油箱的承压侧...",
    evidence_text: "【规范参考内容示例】",
    options_text: "A. 贴合面密封、压力侧\nB. 包胶密封、紧固件处",
    answer_format: "选项字母",
    mode_label: "单选题",
    sub_questions: "- 子问题1\n- 子问题2",
    doc_a: "CPS1000",
    doc_b: "CPS7251",
  },
  null,
  2,
);

function parseVariables(text: string): Record<string, unknown> {
  try {
    return text.trim() ? JSON.parse(text) : {};
  } catch {
    return {};
  }
}

function toDraft(detail: PromptDetail): PromptDraft {
  return {
    description: detail.template.description ?? detail.description ?? "",
    model_preference:
      detail.template.model_preference ?? detail.model_preference ?? "",
    max_tokens: detail.template.max_tokens ?? detail.max_tokens ?? 800,
    temperature: detail.template.temperature ?? detail.temperature ?? 0.3,
    system: detail.template.system ?? "",
    user: detail.template.user ?? "",
    variables: (detail.template.variables ?? detail.variables ?? []).join(", "),
    weight: detail.template.weight ?? 0,
  };
}

export function usePrompts() {
  const [templates, setTemplates] = useState<PromptSummary[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [selectedVersion, setSelectedVersion] = useState("");
  const [detail, setDetail] = useState<PromptDetail | null>(null);
  const [draft, setDraft] = useState<PromptDraft>({
    description: "",
    model_preference: "",
    max_tokens: 800,
    temperature: 0.3,
    system: "",
    user: "",
    variables: "",
    weight: 0,
  });
  const [variablesText, setVariablesText] = useState(SAMPLE_VARIABLES);
  const [rendered, setRendered] = useState<PromptRender | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let alive = true;
    fetchApi<{ templates: PromptSummary[] }>("/api/admin/prompts")
      .then((data) => {
        if (!alive) return;
        const items = data.templates ?? [];
        setTemplates(items);
        setSelectedId((prev) => prev || items[0]?.id || "");
        setSelectedVersion((prev) => prev || items[0]?.active_version || "");
      })
      .catch((err) =>
        setError(err instanceof Error ? err.message : "加载模板失败"),
      )
      .finally(() => setLoading(false));
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    let alive = true;
    setDetail(null);
    fetchApi<PromptDetail>(
      `/api/admin/prompts/${encodeURIComponent(selectedId)}${selectedVersion ? `?version=${encodeURIComponent(selectedVersion)}` : ""}`,
    )
      .then((data) => {
        if (!alive) return;
        setDetail(data);
        setSelectedVersion(data.selected_version || data.active_version);
        setDraft(toDraft(data));
        setRendered(null);
      })
      .catch((err) =>
        setError(err instanceof Error ? err.message : "加载模板详情失败"),
      );
    return () => {
      alive = false;
    };
  }, [selectedId, selectedVersion]);

  function selectTemplate(id: string, version: string) {
    setSelectedId(id);
    setSelectedVersion(version);
  }

  async function refreshTemplates() {
    const data = await fetchApi<{ templates: PromptSummary[] }>(
      "/api/admin/prompts",
    );
    setTemplates(data.templates ?? []);
  }

  async function saveTemplate() {
    if (!selectedId) return;
    setSaving(true);
    setError("");
    try {
      await fetchApi(`/api/admin/prompts/${encodeURIComponent(selectedId)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          version: selectedVersion || undefined,
          active_version: selectedVersion || undefined,
          description: draft.description,
          model_preference: draft.model_preference,
          max_tokens: draft.max_tokens,
          temperature: draft.temperature,
          system: draft.system,
          user: draft.user,
          variables: draft.variables
            .split(",")
            .map((item) => item.trim())
            .filter(Boolean),
          weight: draft.weight,
        }),
      });
      await refreshTemplates();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }

  async function renderTemplate() {
    if (!selectedId) return;
    setTesting(true);
    setError("");
    try {
      const payload = parseVariables(variablesText);
      const data = await fetchApi<PromptRender>(
        `/api/admin/prompts/${encodeURIComponent(selectedId)}/render`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            version: selectedVersion || undefined,
            variables: payload,
          }),
        },
      );
      setRendered(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "测试失败");
    } finally {
      setTesting(false);
    }
  }

  return {
    templates,
    selectedId,
    selectedVersion,
    detail,
    draft,
    setDraft,
    variablesText,
    setVariablesText,
    rendered,
    loading,
    saving,
    testing,
    error,
    selectTemplate,
    setSelectedVersion,
    saveTemplate,
    renderTemplate,
  };
}
