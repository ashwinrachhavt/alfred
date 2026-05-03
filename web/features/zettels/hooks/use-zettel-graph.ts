import { queryOptions, useQuery } from "@tanstack/react-query";

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

const FIVE_MINUTES = 5 * 60 * 1000;

export const zettelGraphQueryKey = ["zettels", "graph"] as const;

export const zettelGraphQueryOptions = queryOptions<ApiZettelGraph>({
  queryKey: zettelGraphQueryKey,
  queryFn: () => apiFetch<ApiZettelGraph>(apiRoutes.zettels.graph),
  staleTime: FIVE_MINUTES,
});

export function useZettelGraph() {
  return useQuery(zettelGraphQueryOptions);
}
