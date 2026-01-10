import { apiFetch } from "@/lib/api/client";

import type { WebSearchResponse } from "@/lib/api/types/web";

export type WebSearchParams = {
  q: string;
  searx_k?: number;
  categories?: string | null;
  time_range?: string | null;
};

export async function webSearch(params: WebSearchParams): Promise<WebSearchResponse> {
  const query = new URLSearchParams();
  query.set("q", params.q);
  if (typeof params.searx_k === "number") query.set("searx_k", String(params.searx_k));
  if (params.categories) query.set("categories", params.categories);
  if (params.time_range) query.set("time_range", params.time_range);
  return apiFetch<WebSearchResponse>(`/api/web/search?${query.toString()}`, { cache: "no-store" });
}

