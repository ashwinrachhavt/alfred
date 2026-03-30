"use client";

import { useMemo } from "react";

import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api/client";
import { apiRoutes } from "@/lib/api/routes";
import { useExplorerDocuments } from "@/features/documents/queries";

import { KnowledgeScore } from "./knowledge-score";

type RetentionMetric = { retention_rate_30d: number; sample_size: number };
type GraphData = { nodes: { id: number; degree: number }[]; edges: unknown[] };

export function LiveKnowledgeScore() {
  const retentionQuery = useQuery({
    queryKey: ["learning", "retention"],
    queryFn: () => apiFetch<RetentionMetric>(apiRoutes.learning.retentionMetrics),
    staleTime: 300_000,
  });

  const graphQuery = useQuery({
    queryKey: ["zettels", "graph"],
    queryFn: () => apiFetch<GraphData>(apiRoutes.zettels.graph),
    staleTime: 300_000,
  });

  const { data: explorerData } = useExplorerDocuments({ limit: 200 });

  const retention = Math.round((retentionQuery.data?.retention_rate_30d ?? 0) * 100);

  const coverage = useMemo(() => {
    const items = explorerData?.pages.flatMap((p) => p.items) ?? [];
    const topics = new Set(items.map((i) => i.primary_topic).filter(Boolean));
    return Math.min(100, topics.size * 10);
  }, [explorerData]);

  const connections = useMemo(() => {
    const nodeCount = graphQuery.data?.nodes?.length ?? 0;
    const edgeCount = graphQuery.data?.edges?.length ?? 0;
    if (nodeCount === 0) return 0;
    return Math.min(100, Math.round((edgeCount / nodeCount) * 25));
  }, [graphQuery.data]);

  return <KnowledgeScore retention={retention} coverage={coverage} connections={connections} />;
}
