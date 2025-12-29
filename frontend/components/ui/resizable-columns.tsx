"use client";

import type { ReactNode } from "react";
import { useEffect, useMemo, useRef } from "react";

export type ResizableColumnsProps = {
  left: ReactNode;
  right: ReactNode;
  leftWidthPx: number;
  onLeftWidthPxChange: (next: number) => void;
  minLeftPx?: number;
  minRightPx?: number;
  storageKey?: string;
};

export function ResizableColumns({
  left,
  right,
  leftWidthPx,
  onLeftWidthPxChange,
  minLeftPx = 320,
  minRightPx = 320,
  storageKey,
}: ResizableColumnsProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const draggingRef = useRef(false);

  const clampedLeftWidthPx = useMemo(() => Math.max(minLeftPx, leftWidthPx), [leftWidthPx, minLeftPx]);

  useEffect(() => {
    if (!storageKey) return;
    try {
      window.localStorage.setItem(storageKey, String(clampedLeftWidthPx));
    } catch {
      // ignore; persistence is optional
    }
  }, [clampedLeftWidthPx, storageKey]);

  useEffect(() => {
    function onMove(e: PointerEvent) {
      if (!draggingRef.current) return;
      const el = containerRef.current;
      if (!el) return;
      const rect = el.getBoundingClientRect();
      const next = e.clientX - rect.left;
      const maxLeft = rect.width - minRightPx;
      onLeftWidthPxChange(Math.min(Math.max(next, minLeftPx), maxLeft));
    }

    function onUp() {
      draggingRef.current = false;
    }

    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    window.addEventListener("pointercancel", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      window.removeEventListener("pointercancel", onUp);
    };
  }, [minLeftPx, minRightPx, onLeftWidthPxChange]);

  return (
    <div ref={containerRef} className="flex h-full min-h-0 w-full">
      <div className="min-h-0" style={{ width: clampedLeftWidthPx }}>
        {left}
      </div>
      <div
        className="group relative w-2 shrink-0 cursor-col-resize"
        onPointerDown={(e) => {
          e.preventDefault();
          draggingRef.current = true;
        }}
        role="separator"
        aria-orientation="vertical"
      >
        <div className="absolute inset-y-0 left-1/2 w-px -translate-x-1/2 bg-border group-hover:bg-foreground/30" />
      </div>
      <div className="min-h-0 flex-1">{right}</div>
    </div>
  );
}
