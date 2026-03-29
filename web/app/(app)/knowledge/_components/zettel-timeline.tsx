"use client";

import { useMemo } from "react";

import { format, isToday, isYesterday, isThisWeek, isThisYear } from "date-fns";
import { Circle } from "lucide-react";

import { cn } from "@/lib/utils";
import { BloomBadge } from "./bloom-badge";
import type { Zettel } from "./mock-data";

type Props = {
  zettels: Zettel[];
  selectedId: string | null;
  onSelect: (id: string) => void;
};

type DateGroup = {
  label: string;
  zettels: Zettel[];
};

function formatDateLabel(dateStr: string): string {
  const date = new Date(dateStr);
  if (isNaN(date.getTime())) return "Unknown date";
  if (isToday(date)) return "Today";
  if (isYesterday(date)) return "Yesterday";
  if (isThisWeek(date)) return format(date, "EEEE");
  if (isThisYear(date)) return format(date, "MMMM d");
  return format(date, "MMMM d, yyyy");
}

function groupByDate(zettels: Zettel[]): DateGroup[] {
  const sorted = [...zettels].sort(
    (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime(),
  );

  const groups = new Map<string, Zettel[]>();
  for (const z of sorted) {
    const label = formatDateLabel(z.createdAt);
    if (!groups.has(label)) groups.set(label, []);
    groups.get(label)!.push(z);
  }

  return Array.from(groups.entries()).map(([label, zettels]) => ({ label, zettels }));
}

export function ZettelTimeline({ zettels, selectedId, onSelect }: Props) {
  const groups = useMemo(() => groupByDate(zettels), [zettels]);

  if (zettels.length === 0) return null;

  return (
    <div className="max-w-2xl mx-auto">
      {groups.map((group) => (
        <div key={group.label} className="mb-6">
          {/* Date header */}
          <div className="sticky top-0 z-10 bg-background/95 backdrop-blur-sm pb-2 pt-1">
            <span className="font-mono text-[10px] uppercase tracking-widest text-[var(--alfred-text-tertiary)]">
              {group.label}
            </span>
          </div>

          {/* Timeline items */}
          <div className="relative ml-3 border-l border-[var(--alfred-ruled-line)] pl-6">
            {group.zettels.map((z) => (
              <button
                key={z.id}
                onClick={() => onSelect(z.id)}
                className={cn(
                  "group relative mb-3 w-full rounded-lg border p-4 text-left transition-all duration-150",
                  selectedId === z.id
                    ? "border-primary bg-[var(--alfred-accent-subtle)] shadow-sm"
                    : "border-[var(--border)] hover:border-[var(--border-strong)] hover:bg-[var(--alfred-accent-subtle)] hover:-translate-y-px hover:shadow-sm",
                )}
              >
                {/* Timeline dot */}
                <div className="absolute -left-[31px] top-5 flex size-4 items-center justify-center rounded-full border bg-background">
                  <Circle
                    className={cn(
                      "size-2",
                      selectedId === z.id ? "fill-primary text-primary" : "fill-[var(--alfred-text-tertiary)] text-[var(--alfred-text-tertiary)]",
                    )}
                  />
                </div>

                {/* Content */}
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <h3 className="font-serif text-[15px] leading-snug">{z.title}</h3>
                    <p className="mt-1 line-clamp-2 text-[13px] leading-relaxed text-muted-foreground">
                      {z.summary}
                    </p>
                    <div className="mt-2 flex items-center gap-2">
                      {z.tags.slice(0, 3).map((tag) => (
                        <span
                          key={tag}
                          className="rounded-sm bg-[var(--alfred-accent-subtle)] px-2 py-0.5 font-mono text-[9px] uppercase tracking-wider text-primary"
                        >
                          {tag}
                        </span>
                      ))}
                      <span className="font-mono text-[10px] text-[var(--alfred-text-tertiary)]">
                        {format(new Date(z.createdAt), "h:mm a")}
                      </span>
                    </div>
                  </div>
                  <BloomBadge level={z.bloomLevel} />
                </div>

                {/* Connection count */}
                {z.connections.length > 0 && (
                  <div className="mt-2 font-mono text-[10px] text-[var(--alfred-text-tertiary)]">
                    {z.connections.length} connection{z.connections.length !== 1 ? "s" : ""}
                  </div>
                )}
              </button>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
