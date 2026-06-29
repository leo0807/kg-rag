"use client";

import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";

/**
 * Wraps page content so every route change triggers:
 *   1. A thin cyan progress bar that sweeps across the top
 *   2. A slide-up-fade entry on the content
 */
export default function RouteTransition({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [key, setKey] = useState(pathname);
  const [barVisible, setBarVisible] = useState(false);
  const prev = useRef(pathname);

  useEffect(() => {
    if (prev.current === pathname) return;
    prev.current = pathname;
    setBarVisible(true);
    setKey(pathname);
    const t = setTimeout(() => setBarVisible(false), 600);
    return () => clearTimeout(t);
  }, [pathname]);

  return (
    <div className="relative flex-1 flex flex-col min-h-0">
      {/* Route progress bar */}
      <div
        className="absolute top-0 left-0 right-0 h-[3px] z-50 pointer-events-none overflow-hidden"
        style={{ opacity: barVisible ? 1 : 0, transition: "opacity 0.25s ease" }}
      >
        <div
          style={{
            height: "100%",
            background: "linear-gradient(90deg, transparent 0%, #06b6d4 30%, #22d3ee 55%, #818cf8 80%, transparent 100%)",
            boxShadow: "0 0 12px rgba(34,211,238,0.8), 0 0 24px rgba(34,211,238,0.4)",
            animation: barVisible ? "progress-bar 0.55s ease-out both" : "none",
          }}
        />
      </div>

      {/* Page content — re-keyed on route change triggers slide-up-fade */}
      <div
        key={key}
        suppressHydrationWarning
        className="flex-1 overflow-auto page-animated"
        style={{ animation: "page-enter 0.45s cubic-bezier(0.22,1,0.36,1) both" }}
      >
        {children}
      </div>
    </div>
  );
}
