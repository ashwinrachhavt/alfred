import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/client";
import { apiRoutes } from "@/lib/api/routes";

export type GraphNode = {
  id: number;
  title: string;
  topic: string | null;
  tags: string[];
  degree: number;
  status: string;
  cluster_id: number | null;
  created_at: string | null;
  updated_at: string | null;
  due_at: string | null;
  importance: number;
};

export type GraphEdge = {
  source: number;
  target: number;
  type: string;
  score: number | null;
};

export type GraphCluster = {
  id: number;
  name: string;
  card_ids: number[];
  color: string;
};

export type GraphGap = {
  id: number;
  title: string;
  inbound_link_count: number;
};

export type ExtendedGraphData = {
  nodes: GraphNode[];
  edges: GraphEdge[];
  clusters: GraphCluster[];
  gaps: GraphGap[];
  meta: {
    total_cards: number;
    total_edges: number;
    embedding_coverage_pct: number;
    cluster_count: number;
  } | null;
};

export function useExtendedGraph(enabled = true) {
  return useQuery<ExtendedGraphData>({
    queryKey: ["zettel-graph-extended"],
    queryFn: () =>
      apiFetch<ExtendedGraphData>(
        `${apiRoutes.zettels.graph}?include=clusters,gaps`
      ),
    staleTime: 5 * 60 * 1000,
    enabled,
  });
}
