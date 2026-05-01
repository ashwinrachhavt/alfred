import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api/client";
import { apiRoutes } from "@/lib/api/routes";

export type ApiGraphNode = {
  id: number;
  title: string;
  topic: string | null;
  tags: string[];
  importance: number;
  status: string;
  degree: number;
};

export type ApiGraphEdge = {
  id: number;
  from: number;
  to: number;
  type: string;
  bidirectional: boolean;
};

export type ApiZettelGraph = {
  nodes: ApiGraphNode[];
  edges: ApiGraphEdge[];
};

export function useZettelGraph() {
  return useQuery<ApiZettelGraph>({
    queryKey: ["zettels", "graph"],
    queryFn: () => apiFetch<ApiZettelGraph>(apiRoutes.zettels.graph, { cache: "no-store" }),
    staleTime: 30_000,
  });
}
