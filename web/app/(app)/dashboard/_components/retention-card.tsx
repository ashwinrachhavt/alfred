"use client";

import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api/client";
import { apiRoutes } from "@/lib/api/routes";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

type RetentionMetric = { retention_rate_30d: number; sample_size: number };

export function RetentionCard() {
  const { data, isLoading } = useQuery({
    queryKey: ["learning", "retention"],
    queryFn: () => apiFetch<RetentionMetric>(apiRoutes.learning.retentionMetrics),
    staleTime: 300_000,
  });

  const dueQuery = useQuery({
    queryKey: ["zettels", "reviews", "due"],
    queryFn: () => apiFetch<unknown[]>(apiRoutes.zettels.reviewsDue),
    staleTime: 300_000,
  });

  return (
    <Card>
      <CardContent className="pt-5 space-y-3">
        <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--alfred-text-tertiary)]">
          Retention
        </div>
        {isLoading ? (
          <Skeleton className="h-16 w-full" />
        ) : (
          <>
            <div className="font-data text-3xl font-semibold tabular-nums">
              {Math.round((data?.retention_rate_30d ?? 0) * 100)}%
              <span className="ml-2 font-mono text-xs font-normal text-muted-foreground">30-day</span>
            </div>
            <div className="font-mono text-xs text-muted-foreground">
              {dueQuery.data?.length ?? 0} concepts due for review
            </div>
            <Button size="sm" variant="outline" className="font-mono text-xs">
              Start Review
            </Button>
          </>
        )}
      </CardContent>
    </Card>
  );
}
