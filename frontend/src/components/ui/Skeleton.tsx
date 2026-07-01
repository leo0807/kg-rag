/** Unified skeleton loading components — use .skeleton CSS class (shimmer via globals.css) */

interface Props { className?: string }

export function SkeletonLine({ className = "" }: Props) {
  return <div className={`skeleton skeleton-md w-full ${className}`} />;
}

export function SkeletonStat() {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl px-4 py-4 flex items-center gap-3">
      <div className="skeleton w-9 h-9 rounded-lg shrink-0" />
      <div className="flex-1 space-y-2 min-w-0">
        <div className="skeleton skeleton-xl w-16 rounded" />
        <div className="skeleton skeleton-sm w-20 rounded" />
      </div>
    </div>
  );
}

export function SkeletonCard({ rows = 3 }: { rows?: number }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-3">
      <div className="skeleton skeleton-md w-2/3 rounded" />
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="skeleton skeleton-sm rounded" style={{ width: `${90 - i * 12}%` }} />
      ))}
    </div>
  );
}

export function SkeletonRow() {
  return (
    <div className="flex items-center gap-4 py-2.5 border-b border-gray-800/60">
      <div className="skeleton skeleton-sm w-8 rounded" />
      <div className="skeleton skeleton-sm flex-1 rounded" />
      <div className="skeleton skeleton-sm w-20 rounded" />
      <div className="skeleton skeleton-sm w-16 rounded" />
    </div>
  );
}

export function SkeletonTable({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-0.5">
      {Array.from({ length: rows }).map((_, i) => <SkeletonRow key={i} />)}
    </div>
  );
}

export function SkeletonGrid({ cols = 4, rows = 1 }: { cols?: number; rows?: number }) {
  return (
    <div className={`grid grid-cols-${cols} gap-3`}>
      {Array.from({ length: cols * rows }).map((_, i) => <SkeletonStat key={i} />)}
    </div>
  );
}

export function SkeletonText({ lines = 3, className = "" }: { lines?: number; className?: string }) {
  const widths = ["w-full", "w-5/6", "w-4/6", "w-3/4", "w-2/3"];
  return (
    <div className={`space-y-2 ${className}`}>
      {Array.from({ length: lines }).map((_, i) => (
        <div key={i} className={`skeleton skeleton-sm rounded ${widths[i % widths.length]}`} />
      ))}
    </div>
  );
}

export function LoadingDots({ className = "text-indigo-400" }: Props) {
  return (
    <span className={`loading-dots ${className}`}>
      <span /><span /><span />
    </span>
  );
}
