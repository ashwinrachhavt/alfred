"use client";

import { useMemo } from "react";

import { subDays, format, startOfDay } from "date-fns";

import { useExplorerDocuments } from "@/features/documents/queries";
import { Card, CardContent } from "@/components/ui/card";

export function ActivityStrip() {
  const { data } = useExplorerDocuments({ limit: 100 });

  const dayCounts = useMemo(() => {
    const items = data?.pages.flatMap((p) => p.items) ?? [];
    const now = new Date();
    const days = Array.from({ length: 7 }, (_, i) => {
      const date = startOfDay(subDays(now, 6 - i));
      return { date, label: format(date, "EEE"), count: 0 };
    });

    for (const item of items) {
      const itemDate = startOfDay(new Date(item.created_at));
      const match = days.find((d) => d.date.getTime() === itemDate.getTime());
      if (match) match.count += 1;
    }
    return days;
  }, [data]);

  const maxCount = Math.max(1, ...dayCounts.map((d) => d.count));

  return (
    <Card>
      <CardContent className="pt-5">
        <div className="mb-4 font-mono text-[10px] uppercase tracking-widest text-[var(--alfred-text-tertiary)]">
          Activity (7 days)
        </div>
        <div className="flex items-end gap-2 h-20">
          {dayCounts.map((d) => (
            <div key={d.label} className="flex flex-1 flex-col items-center gap-1.5">
              <div
                className="w-full rounded-sm bg-primary transition-all duration-200"
                style={{ height: `${Math.max(4, (d.count / maxCount) * 100)}%` }}
              />
              <span className="font-mono text-[10px] text-[var(--alfred-text-tertiary)]">{d.label}</span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
