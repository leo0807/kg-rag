"use client";

type VersionInfo = {
  name: string;
  weight: number;
};

type Props = {
  versions: VersionInfo[];
  selectedVersion: string;
};

export function PromptVersionBadges({ versions, selectedVersion }: Props) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-4">
      <div className="mb-2 text-sm font-semibold text-slate-100">版本信息</div>
      <div className="flex flex-wrap gap-2">
        {versions.map((version) => (
          <span
            key={version.name}
            className={`rounded-full px-3 py-1 text-xs ${
              version.name === selectedVersion
                ? "bg-indigo-500/20 text-indigo-200"
                : "bg-slate-800 text-slate-300"
            }`}
          >
            {version.name} · weight {version.weight}
          </span>
        ))}
      </div>
    </div>
  );
}
