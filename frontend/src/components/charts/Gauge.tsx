"use client";
import { ChartWrapper, fmtNum } from "./shared";

export type GaugeProps = {
  value: number;
  max?: number;
  title?: string;
  unit?: string;
  size?: number;
  loading?: boolean;
  thresholds?: [number, number]; // [warn, danger] percentages
  id?: string;
};

export function Gauge({
  value, max = 100, title, unit = "%", size = 140,
  thresholds = [60, 80], id,
}: GaugeProps) {
  const pct = Math.min(value / max, 1);
  const angle = -135 + pct * 270; // sweep from -135° to +135°
  const r = size * 0.38;
  const cx = size / 2;
  const cy = size * 0.58;

  const toRad = (deg: number) => (deg * Math.PI) / 180;
  const arcX = (deg: number) => cx + r * Math.cos(toRad(deg - 90));
  const arcY = (deg: number) => cy + r * Math.sin(toRad(deg - 90));

  const track = `M ${arcX(-135)} ${arcY(-135)} A ${r} ${r} 0 1 1 ${arcX(135)} ${arcY(135)}`;
  const fill  = `M ${arcX(-135)} ${arcY(-135)} A ${r} ${r} 0 ${pct > 0.5 ? 1 : 0} 1 ${arcX(angle)} ${arcY(angle)}`;

  const color =
    pct * 100 >= thresholds[1] ? "#EF4444" :
    pct * 100 >= thresholds[0] ? "#F59E0B" :
    "#3B82F6";

  return (
    <ChartWrapper title={title} id={id}>
      <div className="flex justify-center">
        <svg width={size} height={size * 0.75} overflow="visible">
          {/* Track */}
          <path d={track} fill="none" stroke="#374151" strokeWidth={10} strokeLinecap="round" />
          {/* Fill */}
          {pct > 0 && (
            <path d={fill} fill="none" stroke={color} strokeWidth={10} strokeLinecap="round" />
          )}
          {/* Needle */}
          <line
            x1={cx} y1={cy}
            x2={cx + (r - 12) * Math.cos(toRad(angle - 90))}
            y2={cy + (r - 12) * Math.sin(toRad(angle - 90))}
            stroke={color} strokeWidth={2.5} strokeLinecap="round"
          />
          <circle cx={cx} cy={cy} r={5} fill={color} />
          {/* Value */}
          <text x={cx} y={cy + 24} textAnchor="middle" fill="white" fontSize={size * 0.16} fontWeight="bold">
            {fmtNum(value)}
          </text>
          <text x={cx} y={cy + 36} textAnchor="middle" fill="#9CA3AF" fontSize={size * 0.08}>
            {unit}
          </text>
        </svg>
      </div>
    </ChartWrapper>
  );
}
