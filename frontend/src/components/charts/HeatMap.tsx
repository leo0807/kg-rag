"use client";
import { ChartEmpty, ChartLoading, ChartWrapper } from "./shared";

export type HeatMapProps = {
  data: { x: string; y: string; value: number }[];
  title?: string;
  height?: number;
  loading?: boolean;
  id?: string;
  colorScale?: [string, string]; // [low, high]
};

function lerp(a: number, b: number, t: number) {
  return a + (b - a) * t;
}

function hexToRgb(hex: string): [number, number, number] {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return [r, g, b];
}

function interpolateColor(low: string, high: string, t: number): string {
  const [r1, g1, b1] = hexToRgb(low);
  const [r2, g2, b2] = hexToRgb(high);
  return `rgb(${Math.round(lerp(r1, r2, t))},${Math.round(lerp(g1, g2, t))},${Math.round(lerp(b1, b2, t))})`;
}

export function HeatMap({
  data, title, height = 280, loading, id,
  colorScale = ["#1E3A5F", "#3B82F6"],
}: HeatMapProps) {
  if (loading) return <ChartLoading height={height} />;
  if (!data.length) return <ChartEmpty height={height} />;

  const xs = [...new Set(data.map(d => d.x))].sort();
  const ys = [...new Set(data.map(d => d.y))].sort();
  const max = Math.max(...data.map(d => d.value), 1);

  const cellSize = Math.min(
    Math.floor((height - 40) / ys.length),
    40,
  );

  return (
    <ChartWrapper title={title} id={id}>
      <div style={{ height, overflowX: "auto" }}>
        <div className="flex">
          {/* Y-axis labels */}
          <div className="flex flex-col" style={{ marginTop: 20 }}>
            {ys.map(y => (
              <div key={y} className="text-xs text-gray-400 flex items-center justify-end pr-2"
                style={{ height: cellSize, minWidth: 60 }}>
                {y}
              </div>
            ))}
          </div>
          {/* Grid */}
          <div>
            {/* X labels */}
            <div className="flex">
              {xs.map(x => (
                <div key={x} className="text-xs text-gray-400 text-center"
                  style={{ width: cellSize, fontSize: 10 }}>
                  {x}
                </div>
              ))}
            </div>
            {ys.map(y => (
              <div key={y} className="flex">
                {xs.map(x => {
                  const d = data.find(dd => dd.x === x && dd.y === y);
                  const v = d?.value ?? 0;
                  const t = v / max;
                  return (
                    <div
                      key={x}
                      title={`${x}, ${y}: ${v}`}
                      style={{
                        width: cellSize, height: cellSize,
                        background: interpolateColor(colorScale[0], colorScale[1], t),
                        border: "1px solid #111827",
                      }}
                    />
                  );
                })}
              </div>
            ))}
          </div>
        </div>
      </div>
    </ChartWrapper>
  );
}
