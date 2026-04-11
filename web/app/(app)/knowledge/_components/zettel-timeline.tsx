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
    <div className="mx-auto max-w-2xl">
      {groups.map((group) => (
        <div key={group.label} className="mb-6">
          {/* Date header */}
          <div className="bg-background/95 sticky top-0 z-10 pt-1 pb-2 backdrop-blur-sm">
            <span className="text-[10px] font-medium tracking-widest text-[var(--alfred-text-tertiary)] uppercase">
              {group.label}
            </span>
          </div>

          {/* Timeline items */}
          <div className="relative ml-3 border-l border-[var(--alfred-ruled-line)] pl-6">
            {group.zettels.map((z) => {
              const preview = z.preview ?? z.summary;

              return (
                <button
                  key={z.id}
                  onClick={() => onSelect(z.id)}
                  className={cn(
                    "group relative mb-3 w-full rounded-lg border p-4 text-left transition-all duration-150",
                    selectedId === z.id
                      ? "border-primary bg-[var(--alfred-accent-subtle)] shadow-sm"
                      : "border-[var(--border)] hover:-translate-y-px hover:border-[var(--border-strong)] hover:bg-[var(--alfred-accent-subtle)] hover:shadow-sm",
                  )}
                >
                  {/* Timeline dot */}
                  <div className="bg-background absolute top-5 -left-[31px] flex size-4 items-center justify-center rounded-full border">
                    <Circle
                      className={cn(
                        "size-2",
                        selectedId === z.id
                          ? "fill-primary text-primary"
                          : "fill-[var(--alfred-text-tertiary)] text-[var(--alfred-text-tertiary)]",
                      )}
                    />
                  </div>

                  {/* Content */}
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <h3 className="text-[15px] leading-snug">{z.title}</h3>
                      {preview ? (
                        <p className="text-muted-foreground mt-1 line-clamp-2 text-[13px] leading-relaxed">
                          {preview}
                        </p>
                      ) : null}
                      <div className="mt-2 flex items-center gap-2">
                        {z.tags.slice(0, 3).map((tag) => (
                          <span
                            key={tag}
                            className="text-primary rounded-sm bg-[var(--alfred-accent-subtle)] px-2 py-0.5 text-[9px] font-medium tracking-wider uppercase"
                          >
                            {tag}
                          </span>
                        ))}
                        <span className="text-[10px] text-[var(--alfred-text-tertiary)]">
                          {format(new Date(z.createdAt), "h:mm a")}
                        </span>
                      </div>
                    </div>
                    <BloomBadge level={z.bloomLevel} />
                  </div>

                  {/* Connection count */}
                  {z.connections.length > 0 && (
                    <div className="mt-2 text-[10px] text-[var(--alfred-text-tertiary)]">
                      {z.connections.length} connection{z.connections.length !== 1 ? "s" : ""}
                    </div>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
