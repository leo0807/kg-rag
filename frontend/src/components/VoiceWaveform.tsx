"use client";

import { useEffect, useRef } from "react";

interface Props {
  active: boolean;
  color?: string;
}

/** Animated waveform bars while recording. */
export function VoiceWaveform({ active, color = "#818cf8" }: Props) {
  const bars = 5;
  const refs = useRef<(HTMLSpanElement | null)[]>([]);

  useEffect(() => {
    if (!active) {
      refs.current.forEach((b) => b && (b.style.transform = "scaleY(0.2)"));
      return;
    }
    const intervals = refs.current.map((bar, i) => {
      if (!bar) return null;
      return setInterval(() => {
        const h = 0.2 + Math.random() * 0.8;
        bar.style.transform = `scaleY(${h})`;
      }, 120 + i * 30);
    });
    return () => intervals.forEach((t) => t && clearInterval(t));
  }, [active]);

  return (
    <span className="inline-flex items-center gap-0.5 h-4">
      {Array.from({ length: bars }).map((_, i) => (
        <span
          key={i}
          ref={(el) => { refs.current[i] = el; }}
          className="w-0.5 h-full rounded-full transition-transform duration-100 origin-bottom"
          style={{ background: color, transform: "scaleY(0.2)" }}
        />
      ))}
    </span>
  );
}
