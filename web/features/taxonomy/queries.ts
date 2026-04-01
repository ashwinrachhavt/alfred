import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getTaxonomyTree,
  listTaxonomyDomains,
  reclassifyAll,
  createTaxonomyNode,
  updateTaxonomyNode,
  deleteTaxonomyNode,
} from "@/lib/api/taxonomy";
import type {
  CreateTaxonomyNodePayload,
  UpdateTaxonomyNodePayload,
} from "@/lib/api/types/taxonomy";

export function useTaxonomyDomains() {
  return useQuery({
    queryKey: ["taxonomy", "domains"],
    queryFn: listTaxonomyDomains,
    staleTime: 600_000,
  });
}

export function useTaxonomyTree(domain?: string) {
  return useQuery({
    queryKey: ["taxonomy", "tree", domain ?? "all"],
    queryFn: () => getTaxonomyTree(domain),
    staleTime: 600_000,
  });
}

export function useReclassifyAll() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: reclassifyAll,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["taxonomy"] });
    },
  });
}

export function useCreateTaxonomyNode() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: CreateTaxonomyNodePayload) =>
      createTaxonomyNode(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["taxonomy"] });
    },
  });
}

export function useUpdateTaxonomyNode() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      slug,
      payload,
    }: {
      slug: string;
      payload: UpdateTaxonomyNodePayload;
    }) => updateTaxonomyNode(slug, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["taxonomy"] });
    },
  });
}

export function useDeleteTaxonomyNode() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      slug,
      reassignParent,
    }: {
      slug: string;
      reassignParent?: string;
    }) => deleteTaxonomyNode(slug, reassignParent),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["taxonomy"] });
    },
  });
}
