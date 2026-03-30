"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { apiFetch } from "@/lib/api/client";
import { apiRoutes } from "@/lib/api/routes";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

type GraphData = { nodes: { id: number; degree: number }[]; edges: unknown[] };

export function ConnectionsCard() {
  const { data, isLoading } = useQuery({
    queryKey: ["zettels", "graph"],
    queryFn: () => apiFetch<GraphData>(apiRoutes.zettels.graph),
    staleTime: 300_000,
  });

  const nodeCount = data?.nodes.length ?? 0;
  const edgeCount = data?.edges.length ?? 0;
  const density = nodeCount > 0 ? (edgeCount / nodeCount).toFixed(1) : "0";
  const orphans = data?.nodes.filter((n) => n.degree === 0).length ?? 0;

  return (
    <Card>
      <CardContent className="pt-5 space-y-3">
        <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--alfred-text-tertiary)]">
          Connections
        </div>
        {isLoading ? (
          <Skeleton className="h-16 w-full" />
        ) : (
          <>
            <div className="flex gap-6">
              <div>
                <div className="font-data text-3xl font-semibold tabular-nums">{density}</div>
                <div className="font-mono text-[10px] text-muted-foreground">edges/node</div>
              </div>
              <div>
                <div className="font-data text-3xl font-semibold tabular-nums">{orphans}</div>
                <div className="font-mono text-[10px] text-muted-foreground">orphans</div>
              </div>
            </div>
            <Button size="sm" variant="outline" asChild className="font-mono text-xs">
              <Link href="/canvas">Open Canvas</Link>
            </Button>
          </>
        )}
      </CardContent>
    </Card>
  );
}
