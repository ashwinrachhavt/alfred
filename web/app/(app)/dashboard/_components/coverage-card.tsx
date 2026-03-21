"use client";

import { useMemo } from "react";

import { useExplorerDocuments } from "@/features/documents/queries";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
      <CardHeader>
        <CardTitle className="text-base">Coverage</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {isLoading ? (
          <Skeleton className="h-32 w-full" />
        ) : topicCounts.length === 0 ? (
          <p className="text-muted-foreground text-sm">Not enough data yet.</p>
        ) : (
          <>
            <div className="text-2xl font-bold">
              {topicCounts.length} <span className="text-muted-foreground text-sm font-normal">topics</span>
            </div>
            <div className="space-y-1">
              {topicCounts.map(([topic, count]) => (
                <div key={topic} className="flex items-center justify-between text-sm">
                  <span className="truncate">{topic}</span>
                  <span className="text-muted-foreground">{count}</span>
                </div>
              ))}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
