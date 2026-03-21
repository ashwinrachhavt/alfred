"use client";

import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api/client";
import { apiRoutes } from "@/lib/api/routes";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

type RetentionMetric = { retention_rate_30d: number; sample_size: number };

export function RetentionCard() {
  const { data, isLoading } = useQuery({
    queryKey: ["learning", "retention"],
    queryFn: () => apiFetch<RetentionMetric>(apiRoutes.learning.retentionMetrics),
    staleTime: 60_000,
  });

  const dueQuery = useQuery({
    queryKey: ["zettels", "reviews", "due"],
    queryFn: () => apiFetch<unknown[]>(apiRoutes.zettels.reviewsDue),
    staleTime: 60_000,
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Retention</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {isLoading ? (
          <Skeleton className="h-16 w-full" />
        ) : (
          <>
            <div className="text-2xl font-bold">
              {Math.round((data?.retention_rate_30d ?? 0) * 100)}%
              <span className="text-muted-foreground text-sm font-normal ml-2">30-day retention</span>
            </div>
            <div className="text-muted-foreground text-sm">
              {dueQuery.data?.length ?? 0} concepts due for review
            </div>
            <Button size="sm" variant="outline">Start Review Session</Button>
          </>
        )}
      </CardContent>
    </Card>
  );
}
