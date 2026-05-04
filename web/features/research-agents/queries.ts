import { useMutation, useQuery, useQueryClient, queryOptions } from "@tanstack/react-query";

import {
  type ResearchAgentSpec,
  type ResearchAgentSpecCreate,
  type ResearchAgentSpecUpdate,
  createResearchAgent,
  deleteResearchAgent,
  getResearchAgent,
  getToolCatalog,
  listResearchAgents,
  updateResearchAgent,
} from "@/lib/api/research-agents";

export const researchAgentsKeys = {
  all: ["research-agents"] as const,
  list: () => [...researchAgentsKeys.all, "list"] as const,
  byId: (id: number) => [...researchAgentsKeys.all, "by-id", id] as const,
  catalog: () => [...researchAgentsKeys.all, "catalog"] as const,
};

export function researchAgentsListOptions() {
  return queryOptions({
    queryKey: researchAgentsKeys.list(),
    queryFn: listResearchAgents,
    staleTime: 60_000,
  });
}

export function useResearchAgents() {
  return useQuery(researchAgentsListOptions());
}

export function useResearchAgent(id: number | null) {
  return useQuery({
    enabled: id !== null,
    queryKey: id !== null ? researchAgentsKeys.byId(id) : researchAgentsKeys.list(),
    queryFn: () => getResearchAgent(id!),
    staleTime: 60_000,
  });
}

export function useToolCatalog() {
  return useQuery({
    queryKey: researchAgentsKeys.catalog(),
    queryFn: getToolCatalog,
    staleTime: Infinity,
  });
}

export function useCreateResearchAgent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ResearchAgentSpecCreate) => createResearchAgent(body),
    onSuccess: (created: ResearchAgentSpec) => {
      qc.invalidateQueries({ queryKey: researchAgentsKeys.list() });
      qc.setQueryData(researchAgentsKeys.byId(created.id), created);
    },
  });
}

export function useUpdateResearchAgent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body: ResearchAgentSpecUpdate }) =>
      updateResearchAgent(id, body),
    onSuccess: (updated: ResearchAgentSpec) => {
      qc.invalidateQueries({ queryKey: researchAgentsKeys.list() });
      qc.setQueryData(researchAgentsKeys.byId(updated.id), updated);
    },
  });
}

export function useDeleteResearchAgent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => deleteResearchAgent(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: researchAgentsKeys.list() });
    },
  });
}
