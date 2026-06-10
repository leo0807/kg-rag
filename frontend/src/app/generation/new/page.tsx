"use client";

import { fetchApi } from "@/lib/api";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ReferenceDocPicker } from "./ReferenceDocPicker";
import { TemplateSelector } from "./TemplateSelector";
import { WizardStepper } from "./WizardStepper";

const STEPS = ["选择模板", "基本信息", "参考规范", "试验数据", "确认启动"];

interface FormState {
  template_id:        string;
  spec_type:          string;
  spec_name:          string;
  user_requirements:  string;
  target_application: string;
  must_reference:     string;
  reference_docs:     string[];
}

const DEFAULT_FORM: FormState = {
  template_id: "", spec_type: "", spec_name: "",
  user_requirements: "", target_application: "",
  must_reference: "", reference_docs: [],
};

export default function NewGenerationPage() {
  const router = useRouter();
  const [step, setStep]     = useState(0);
  const [form, setForm]     = useState<FormState>(DEFAULT_FORM);
  const [createdId, setCreatedId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError]   = useState("");

  const stepsConfig = STEPS.map((label, i) => ({
    label, done: i < step, active: i === step,
  }));

  const set = (k: keyof FormState, v: string | string[]) =>
    setForm(f => ({ ...f, [k]: v }));

  const canNext = () => {
    if (step === 0) return !!form.template_id;
    if (step === 1) return !!form.spec_name.trim() && !!form.spec_type.trim();
    return true;
  };

  const createTask = async () => {
    setSaving(true);
    setError("");
    try {
      const body = {
        spec_name:         form.spec_name,
        spec_type:         form.spec_type,
        template_id:       form.template_id,
        reference_docs:    form.reference_docs,
        user_requirements: form.user_requirements,
        target_application: form.target_application,
        must_reference:    form.must_reference
          ? form.must_reference.split(/[,，\n]/).map(s => s.trim()).filter(Boolean)
          : [],
        must_include_sections: [],
      };
      const task = await fetchApi<{ id: string }>(
        "/api/generation/tasks", { method: "POST", body: JSON.stringify(body),
          headers: { "Content-Type": "application/json" } }
      );
      setCreatedId(task.id);
      setStep(3);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "创建失败");
    } finally {
      setSaving(false);
    }
  };

  const startGeneration = async () => {
    if (!createdId) return;
    setSaving(true);
    try {
      await fetchApi(`/api/generation/tasks/${createdId}/start`, { method: "POST" });
      router.push(`/generation/${createdId}`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "启动失败");
      setSaving(false);
    }
  };

  return (
    <div className="flex-1 overflow-auto bg-gray-950 p-6">
      <div className="max-w-2xl mx-auto">
        <h1 className="text-lg font-semibold text-gray-100 mb-6">新建规范生成任务</h1>
        <WizardStepper steps={stepsConfig} />

        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 min-h-64">

          {step === 0 && (
            <div>
              <h2 className="text-sm font-medium text-gray-300 mb-3">选择规范模板</h2>
              <TemplateSelector
                value={form.template_id}
                onChange={(tid, stype) => { set("template_id", tid); set("spec_type", stype); }}
              />
            </div>
          )}

          {step === 1 && (
            <div className="space-y-4">
              <h2 className="text-sm font-medium text-gray-300 mb-3">填写基本信息</h2>
              <Field label="规范名称 *" required>
                <input value={form.spec_name} onChange={e => set("spec_name", e.target.value)}
                  placeholder="如：CPSXXXX 密封剂应用规范"
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-indigo-600" />
              </Field>
              <Field label="规范类型 *" required>
                <input value={form.spec_type} onChange={e => set("spec_type", e.target.value)}
                  placeholder="如：密封、复合材料、紧固件…"
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-indigo-600" />
              </Field>
              <Field label="应用场景">
                <input value={form.target_application} onChange={e => set("target_application", e.target.value)}
                  placeholder="如：机身结构密封工艺"
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-indigo-600" />
              </Field>
              <Field label="需求说明">
                <textarea value={form.user_requirements} onChange={e => set("user_requirements", e.target.value)}
                  rows={3} placeholder="描述该规范的核心要求、特殊约束或背景信息…"
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-indigo-600 resize-none" />
              </Field>
            </div>
          )}

          {step === 2 && (
            <div>
              <h2 className="text-sm font-medium text-gray-300 mb-3">选择参考规范</h2>
              <ReferenceDocPicker
                selected={form.reference_docs}
                onChange={ids => set("reference_docs", ids)}
              />
              <div className="mt-4">
                <Field label="必须引用的标准（逗号分隔）">
                  <input value={form.must_reference} onChange={e => set("must_reference", e.target.value)}
                    placeholder="如：HB/T 1001, AMS 3276"
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-indigo-600" />
                </Field>
              </div>
            </div>
          )}

          {step === 3 && createdId && (
            <div className="space-y-4">
              <h2 className="text-sm font-medium text-gray-300 mb-3">上传试验数据（可选）</h2>
              <p className="text-xs text-gray-500">
                任务 ID：<span className="font-mono text-gray-400">{createdId}</span>
              </p>
              <p className="text-xs text-gray-500">
                可跳过此步骤，在任务详情页单独上传。
              </p>
            </div>
          )}

          {step === 4 && (
            <div className="space-y-3">
              <h2 className="text-sm font-medium text-gray-300 mb-3">确认并启动</h2>
              <SummaryRow label="规范名称" value={form.spec_name} />
              <SummaryRow label="规范类型" value={form.spec_type} />
              <SummaryRow label="模板"     value={form.template_id} />
              <SummaryRow label="参考文档" value={form.reference_docs.join(", ") || "无"} />
              {error && <p className="text-xs text-red-400">{error}</p>}
            </div>
          )}
        </div>

        {error && step < 4 && <p className="mt-2 text-xs text-red-400">{error}</p>}

        {/* Navigation */}
        <div className="flex justify-between mt-4">
          <button onClick={() => step > 0 && setStep(s => s - 1)}
            disabled={step === 0}
            className="px-4 py-1.5 text-xs text-gray-500 hover:text-gray-300 disabled:opacity-30">
            上一步
          </button>
          {step < 2 && (
            <button onClick={() => setStep(s => s + 1)} disabled={!canNext()}
              className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white text-xs rounded-lg">
              下一步
            </button>
          )}
          {step === 2 && (
            <button onClick={async () => { await createTask(); if (!error) setStep(3); }}
              disabled={saving}
              className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white text-xs rounded-lg">
              {saving ? "创建中…" : "创建任务"}
            </button>
          )}
          {step === 3 && (
            <button onClick={() => setStep(4)}
              className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs rounded-lg">
              下一步
            </button>
          )}
          {step === 4 && (
            <button onClick={startGeneration} disabled={saving}
              className="px-4 py-1.5 bg-green-600 hover:bg-green-500 disabled:opacity-40 text-white text-xs rounded-lg">
              {saving ? "启动中…" : "启动生成"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function Field({ label, required, children }: {
  label: string; required?: boolean; children: React.ReactNode
}) {
  return (
    <div>
      <label className="block text-xs text-gray-400 mb-1">
        {label}{required && <span className="text-red-500 ml-0.5">*</span>}
      </label>
      {children}
    </div>
  );
}

function SummaryRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-3 text-xs">
      <span className="text-gray-500 w-20 shrink-0">{label}</span>
      <span className="text-gray-200">{value || "—"}</span>
    </div>
  );
}
