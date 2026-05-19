"use client";

import {
  NODE_PROPS,
  NODE_TYPES,
  type NodeType,
  REL_DIRS,
  REL_TYPES,
  type RelDir,
  type RelType,
  TEMPLATES,
} from "../admin/cypher/useCypherBuilder";

export interface AdminCypherFormProps {
  nodeType: NodeType;
  setNodeType: (value: NodeType) => void;
  propKey: string;
  setPropKey: (value: string) => void;
  propVal: string;
  setPropVal: (value: string) => void;
  relType: RelType;
  setRelType: (value: RelType) => void;
  relDir: RelDir;
  setRelDir: (value: RelDir) => void;
  targetType: NodeType | "";
  setTargetType: (value: NodeType | "") => void;
  limitVal: number;
  setLimitVal: (value: number) => void;
  orderBy: string;
  setOrderBy: (value: string) => void;
  buildCypher: () => void;
  applyTemplate: (template: (typeof TEMPLATES)[number]) => void;
}

export function AdminCypherForm({
  nodeType,
  setNodeType,
  propKey,
  setPropKey,
  propVal,
  setPropVal,
  relType,
  setRelType,
  relDir,
  setRelDir,
  targetType,
  setTargetType,
  limitVal,
  setLimitVal,
  orderBy,
  setOrderBy,
  buildCypher,
  applyTemplate,
}: AdminCypherFormProps) {
  const sel =
    "w-full h-8 px-2 bg-gray-800 border border-gray-700 rounded text-xs text-gray-300 outline-none focus:border-indigo-500";

  return (
    <div className="w-68 shrink-0 space-y-4 overflow-auto border-r border-gray-800 p-4 text-xs">
      <div className="shrink-0 border-b border-gray-800 px-6 py-3">
        <div className="flex items-center justify-between gap-3">
          <h1 className="text-base font-semibold text-white">
            Cypher 查询构造器
          </h1>
          <select
            onChange={(e) => {
              const t = TEMPLATES.find((x) => x.label === e.target.value);
              if (t) applyTemplate(t);
              e.target.value = "";
            }}
            defaultValue=""
            className="rounded-lg border border-gray-700 bg-gray-800 px-3 py-1.5 text-xs text-gray-300 outline-none"
          >
            <option value="" disabled>
              选择查询模板…
            </option>
            {TEMPLATES.map((t) => (
              <option key={t.label} value={t.label}>
                {t.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      <Section label="起始节点">
        <select
          value={nodeType}
          onChange={(e) => setNodeType(e.target.value as NodeType)}
          className={`${sel} mb-2`}
        >
          {NODE_TYPES.map((t) => (
            <option key={t}>{t}</option>
          ))}
        </select>
        <div className="flex gap-1">
          <select
            value={propKey}
            onChange={(e) => setPropKey(e.target.value)}
            className="h-7 flex-1 rounded border border-gray-700 bg-gray-800 px-2 text-xs text-gray-300 outline-none"
          >
            <option value="">属性</option>
            {NODE_PROPS[nodeType].map((p) => (
              <option key={p}>{p}</option>
            ))}
          </select>
          <input
            value={propVal}
            onChange={(e) => setPropVal(e.target.value)}
            placeholder="值"
            className="h-7 flex-1 rounded border border-gray-700 bg-gray-800 px-2 text-xs text-gray-300 outline-none"
          />
        </div>
      </Section>

      <Section label="关系">
        <select
          value={relType}
          onChange={(e) => setRelType(e.target.value as RelType)}
          className={`${sel} mb-2`}
        >
          {REL_TYPES.map((t) => (
            <option key={t} value={t}>
              {t || "（无关系）"}
            </option>
          ))}
        </select>
        {relType && (
          <div className="mb-2 flex gap-1">
            {REL_DIRS.map((d) => (
              <button
                key={d}
                type="button"
                onClick={() => setRelDir(d as RelDir)}
                className={`h-7 flex-1 rounded text-xs font-mono transition-colors ${relDir === d ? "bg-indigo-600 text-white" : "bg-gray-800 text-gray-400 hover:text-white"}`}
              >
                {d}
              </button>
            ))}
          </div>
        )}
        {relType && (
          <select
            value={targetType}
            onChange={(e) => setTargetType(e.target.value as NodeType)}
            className={sel}
          >
            <option value="">目标节点（任意）</option>
            {NODE_TYPES.map((t) => (
              <option key={t}>{t}</option>
            ))}
          </select>
        )}
      </Section>

      <Section label="查询选项">
        <div className="space-y-2">
          <LabeledRow label="LIMIT">
            <input
              type="number"
              value={limitVal}
              onChange={(e) =>
                setLimitVal(Math.min(100, Number(e.target.value)))
              }
              min={1}
              max={100}
              className="h-7 flex-1 rounded border border-gray-700 bg-gray-800 px-2 text-xs text-gray-300 outline-none"
            />
          </LabeledRow>
          <LabeledRow label="ORDER BY">
            <input
              value={orderBy}
              onChange={(e) => setOrderBy(e.target.value)}
              placeholder="e.g. s.seq_index DESC"
              className="h-7 flex-1 rounded border border-gray-700 bg-gray-800 px-2 text-xs text-gray-300 outline-none"
            />
          </LabeledRow>
        </div>
      </Section>

      <button
        type="button"
        onClick={buildCypher}
        className="w-full rounded-lg border border-gray-700 bg-gray-800 py-1.5 text-gray-300 transition-colors hover:border-indigo-500"
      >
        生成 Cypher ↑
      </button>
    </div>
  );
}

function Section({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="mb-2 text-[10px] font-bold uppercase tracking-widest text-gray-500">
        {label}
      </div>
      {children}
    </div>
  );
}

function LabeledRow({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="w-16 shrink-0 text-gray-400">{label}</span>
      {children}
    </div>
  );
}
