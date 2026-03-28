import { apiFetch } from "@/lib/api/client";
import type { TaxonomyNode, TaxonomyTreeNode } from "@/lib/api/types/taxonomy";

export async function listTaxonomyDomains(): Promise<TaxonomyNode[]> {
  return apiFetch<TaxonomyNode[]>("/api/taxonomy/domains");
}

export async function getTaxonomyTree(domain?: string): Promise<TaxonomyTreeNode[]> {
  const params = domain ? `?domain=${encodeURIComponent(domain)}` : "";
  return apiFetch<TaxonomyTreeNode[]>(`/api/taxonomy/tree${params}`);
}

export async function reclassifyAll(): Promise<Record<string, number>> {
  return apiFetch<Record<string, number>>("/api/taxonomy/reclassify-all", {
    method: "POST",
  });
}
