"use client";
import { ChartEmpty, ChartLoading, ChartWrapper, COLORS } from "./shared";

export type TimelineEvent = {
  id: string;
  label: string;
  start: string;      // ISO date
  end?: string;       // ISO date
  category?: string;
  color?: string;
};

export type TimelineChartProps = {
  events: TimelineEvent[];
  title?: string;
  height?: number;
  loading?: boolean;
  id?: string;
};

export function TimelineChart({ events, title, height = 280, loading, id }: TimelineChartProps) {
  if (loading) return <ChartLoading height={height} />;
  if (!events.length) return <ChartEmpty height={height} />;

  const dates = events.flatMap(e => [new Date(e.start), e.end ? new Date(e.end) : new Date(e.start)]);
  const minT = Math.min(...dates.map(d => d.getTime()));
  const maxT = Math.max(...dates.map(d => d.getTime()));
  const range = maxT - minT || 1;

  const categories = [...new Set(events.map(e => e.category || "default"))];
  const rowH = Math.min(Math.floor((height - 48) / categories.length), 36);

  const toX = (iso: string) => `${((new Date(iso).getTime() - minT) / range) * 96}%`;

  return (
    <ChartWrapper title={title} id={id}>
      <div style={{ height, overflowY: "auto" }} className="relative">
        {/* Time axis */}
        <div className="flex justify-between px-2 text-xs text-gray-500 mb-2">
          <span>{new Date(minT).toLocaleDateString("zh-CN")}</span>
          <span>{new Date(maxT).toLocaleDateString("zh-CN")}</span>
        </div>

        {categories.map((cat, ci) => {
          const catEvents = events.filter(e => (e.category || "default") === cat);
          return (
            <div key={cat} className="relative flex items-center mb-1" style={{ height: rowH }}>
              <span className="text-xs text-gray-500 w-20 shrink-0 pr-2 truncate">{cat}</span>
              <div className="relative flex-1 h-full">
                <div className="absolute inset-0 border-t border-gray-800" style={{ top: "50%" }} />
                {catEvents.map((ev, i) => {
                  const left = toX(ev.start);
                  const right = ev.end ? `${100 - ((new Date(ev.end).getTime() - minT) / range) * 96}%` : undefined;
                  const color = ev.color || COLORS[ci % COLORS.length];
                  return right ? (
                    <div
                      key={ev.id}
                      title={`${ev.label}\n${ev.start} → ${ev.end}`}
                      className="absolute rounded text-xs text-white px-1 truncate flex items-center"
                      style={{ left, right, top: 4, bottom: 4, background: color }}
                    >
                      {ev.label}
                    </div>
                  ) : (
                    <div
                      key={ev.id}
                      title={ev.label}
                      className="absolute rounded-full"
                      style={{ left, width: 10, height: 10, top: "calc(50% - 5px)", background: color }}
                    />
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </ChartWrapper>
  );
}
