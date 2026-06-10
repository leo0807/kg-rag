import { useCallback, useRef } from "react";

interface Options {
  onLongPress: () => void;
  onPress?: () => void;
  delay?: number;
}

export function useLongPress({ onLongPress, onPress, delay = 500 }: Options) {
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const fired = useRef(false);

  const start = useCallback(() => {
    fired.current = false;
    timer.current = setTimeout(() => {
      fired.current = true;
      onLongPress();
    }, delay);
  }, [onLongPress, delay]);

  const cancel = useCallback(() => {
    if (timer.current) {
      clearTimeout(timer.current);
      timer.current = null;
    }
  }, []);

  const end = useCallback(() => {
    cancel();
    if (!fired.current) onPress?.();
  }, [cancel, onPress]);

  return {
    onTouchStart: start,
    onTouchEnd: end,
    onTouchCancel: cancel,
    onMouseDown: start,
    onMouseUp: end,
    onMouseLeave: cancel,
  };
}
