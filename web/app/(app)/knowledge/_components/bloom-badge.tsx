"use client";

import { cn } from "@/lib/utils";
import { BLOOM_LABELS, BLOOM_COLORS, type BloomLevel } from "./mock-data";

export function BloomBadge({ level, className }: { level: BloomLevel; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 font-mono text-[10px] tabular-nums",
        className,
      )}
    >
      <span
        className="size-[6px] rounded-full"
        style={{ backgroundColor: BLOOM_COLORS[level] }}
      />
      <span style={{ color: BLOOM_COLORS[level] }}>
        {level}/6
      </span>
    </span>
  );
}

export function BloomProgressBar({ level }: { level: BloomLevel }) {
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <span className="font-mono text-[10px] uppercase tracking-widest text-[var(--alfred-text-tertiary)]">
          Bloom Level
        </span>
        <span className="font-mono text-[11px]" style={{ color: BLOOM_COLORS[level] }}>
          {BLOOM_LABELS[level]} ({level}/6)
        </span>
      </div>
      <div className="flex gap-[3px] h-[5px]">
        {([1, 2, 3, 4, 5, 6] as const).map((i) => (
          <div
            key={i}
            className="flex-1 rounded-[2px]"
            style={{
              backgroundColor: i <= level ? BLOOM_COLORS[level] : "var(--border)",
            }}
          />
        ))}
      </div>
    </div>
  );
}
