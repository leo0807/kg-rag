import { useEffect, useRef, useState } from "react";

interface Options {
  onRefresh: () => Promise<void>;
  threshold?: number;
}

/** Returns pull distance (0–threshold) for rendering a pull indicator. */
export function usePullToRefresh(
  ref: React.RefObject<HTMLElement | null>,
  { onRefresh, threshold = 80 }: Options,
) {
  const [pullY, setPullY] = useState(0);
  const [refreshing, setRefreshing] = useState(false);
  const startY = useRef<number | null>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const onStart = (e: TouchEvent) => {
      if (el.scrollTop === 0) startY.current = e.touches[0].clientY;
    };

    const onMove = (e: TouchEvent) => {
      if (startY.current === null || refreshing) return;
      const dy = e.touches[0].clientY - startY.current;
      if (dy > 0) setPullY(Math.min(dy, threshold));
    };

    const onEnd = async () => {
      if (pullY >= threshold && !refreshing) {
        setRefreshing(true);
        try { await onRefresh(); } finally { setRefreshing(false); }
      }
      setPullY(0);
      startY.current = null;
    };

    el.addEventListener("touchstart", onStart, { passive: true });
    el.addEventListener("touchmove", onMove, { passive: true });
    el.addEventListener("touchend", onEnd, { passive: true });
    return () => {
      el.removeEventListener("touchstart", onStart);
      el.removeEventListener("touchmove", onMove);
      el.removeEventListener("touchend", onEnd);
    };
  }, [ref, onRefresh, threshold, pullY, refreshing]);

  return { pullY, refreshing };
}
