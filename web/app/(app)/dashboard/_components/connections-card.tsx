"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { apiFetch } from "@/lib/api/client";
import { apiRoutes } from "@/lib/api/routes";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

type GraphData = { nodes: { id: number; degree: number }[]; edges: unknown[] };

export function ConnectionsCard() {
  const { data, isLoading } = useQuery({
    queryKey: ["zettels", "graph"],
    queryFn: () => apiFetch<GraphData>(apiRoutes.zettels.graph),
    staleTime: 60_000,
  });

  const nodeCount = data?.nodes.length ?? 0;
  const edgeCount = data?.edges.length ?? 0;
  const density = nodeCount > 0 ? (edgeCount / nodeCount).toFixed(1) : "0";
  const orphans = data?.nodes.filter((n) => n.degree === 0).length ?? 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Connections</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {isLoading ? (
          <Skeleton className="h-16 w-full" />
        ) : (
          <>
            <div className="flex gap-6 text-sm">
              <div><span className="text-2xl font-bold">{density}</span> edges/node</div>
              <div><span className="text-2xl font-bold">{orphans}</span> orphans</div>
            </div>
            <Button size="sm" variant="outline" asChild>
              <Link href="/canvas">Open Canvas</Link>
            </Button>
          </>
        )}
      </CardContent>
    </Card>
  );
}
