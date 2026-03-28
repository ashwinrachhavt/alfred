import { useQuery } from "@tanstack/react-query";
import { getTaxonomyTree, listTaxonomyDomains } from "@/lib/api/taxonomy";

export function useTaxonomyDomains() {
  return useQuery({
    queryKey: ["taxonomy", "domains"],
    queryFn: listTaxonomyDomains,
    staleTime: 5 * 60 * 1000,
  });
}

export function useTaxonomyTree(domain?: string) {
  return useQuery({
    queryKey: ["taxonomy", "tree", domain ?? "all"],
    queryFn: () => getTaxonomyTree(domain),
    staleTime: 5 * 60 * 1000,
  });
}
