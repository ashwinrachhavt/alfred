import { apiFetch } from "@/lib/api/client";
import type {
  TaxonomyNode,
  TaxonomyTreeNode,
  CreateTaxonomyNodePayload,
  UpdateTaxonomyNodePayload,
  DeleteTaxonomyNodeResponse,
} from "@/lib/api/types/taxonomy";

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

export async function createTaxonomyNode(
  payload: CreateTaxonomyNodePayload,
): Promise<TaxonomyNode> {
  return apiFetch<TaxonomyNode>("/api/taxonomy/nodes", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function updateTaxonomyNode(
  slug: string,
  payload: UpdateTaxonomyNodePayload,
): Promise<TaxonomyNode> {
  return apiFetch<TaxonomyNode>(`/api/taxonomy/nodes/${slug}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function deleteTaxonomyNode(
  slug: string,
  reassignParent?: string,
): Promise<DeleteTaxonomyNodeResponse> {
  const params = reassignParent
    ? `?reassign_parent=${encodeURIComponent(reassignParent)}`
    : "";
  return apiFetch<DeleteTaxonomyNodeResponse>(
    `/api/taxonomy/nodes/${slug}${params}`,
    { method: "DELETE" },
  );
}
