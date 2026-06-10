import { useEffect, useRef } from "react";

interface SwipeHandlers {
  onSwipeLeft?: () => void;
  onSwipeRight?: () => void;
  onSwipeUp?: () => void;
  onSwipeDown?: () => void;
  threshold?: number;
}

export function useSwipeGesture(
  ref: React.RefObject<HTMLElement | null>,
  handlers: SwipeHandlers,
) {
  const start = useRef<{ x: number; y: number } | null>(null);
  const { onSwipeLeft, onSwipeRight, onSwipeUp, onSwipeDown, threshold = 60 } = handlers;

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const onStart = (e: TouchEvent) => {
      const t = e.touches[0];
      start.current = { x: t.clientX, y: t.clientY };
    };

    const onEnd = (e: TouchEvent) => {
      if (!start.current) return;
      const t = e.changedTouches[0];
      const dx = t.clientX - start.current.x;
      const dy = t.clientY - start.current.y;
      start.current = null;

      if (Math.abs(dx) > Math.abs(dy)) {
        if (dx > threshold) onSwipeRight?.();
        else if (dx < -threshold) onSwipeLeft?.();
      } else {
        if (dy > threshold) onSwipeDown?.();
        else if (dy < -threshold) onSwipeUp?.();
      }
    };

    el.addEventListener("touchstart", onStart, { passive: true });
    el.addEventListener("touchend", onEnd, { passive: true });
    return () => {
      el.removeEventListener("touchstart", onStart);
      el.removeEventListener("touchend", onEnd);
    };
  }, [ref, onSwipeLeft, onSwipeRight, onSwipeUp, onSwipeDown, threshold]);
}
