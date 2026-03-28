"use client";

import { useMemo } from "react";

import { useExplorerDocuments } from "@/features/documents/queries";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export function CoverageCard() {
  const { data, isLoading } = useExplorerDocuments({ limit: 200 });

  const topicCounts = useMemo(() => {
    const items = data?.pages.flatMap((p) => p.items) ?? [];
    const counts: Record<string, number> = {};
    for (const item of items) {
      const topic = item.primary_topic || "Uncategorized";
      counts[topic] = (counts[topic] ?? 0) + 1;
    }
    return Object.entries(counts)
      .sort(([, a], [, b]) => b - a)
      .slice(0, 10);
  }, [data]);

  return (
    <Card>
      <CardContent className="pt-5 space-y-3">
        <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--alfred-text-tertiary)]">
          Coverage
        </div>
        {isLoading ? (
          <Skeleton className="h-32 w-full" />
        ) : topicCounts.length === 0 ? (
          <p className="text-sm text-muted-foreground">Not enough data yet.</p>
        ) : (
          <>
            <div className="font-data text-3xl font-semibold tabular-nums">
              {topicCounts.length}
              <span className="ml-2 font-mono text-xs font-normal text-muted-foreground">topics</span>
            </div>
            <div className="space-y-1">
              {topicCounts.map(([topic, count]) => (
                <div key={topic} className="flex items-center justify-between text-sm">
                  <span className="truncate">{topic}</span>
                  <span className="font-data text-xs tabular-nums text-muted-foreground">{count}</span>
                </div>
              ))}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
