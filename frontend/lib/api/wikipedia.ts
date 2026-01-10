import { apiFetch } from "@/lib/api/client";

import type { WikipediaSearchResponse } from "@/lib/api/types/wikipedia";

export type WikipediaSearchParams = {
  q: string;
  lang?: string;
  top_k_results?: number;
  doc_content_chars_max?: number;
  load_all_available_meta?: boolean;
  load_max_docs?: number;
};

export async function wikipediaSearch(params: WikipediaSearchParams): Promise<WikipediaSearchResponse> {
  const query = new URLSearchParams();
  query.set("q", params.q);
  if (params.lang) query.set("lang", params.lang);
  if (typeof params.top_k_results === "number") query.set("top_k_results", String(params.top_k_results));
  if (typeof params.doc_content_chars_max === "number")
    query.set("doc_content_chars_max", String(params.doc_content_chars_max));
  if (params.load_all_available_meta) query.set("load_all_available_meta", "true");
  if (typeof params.load_max_docs === "number") query.set("load_max_docs", String(params.load_max_docs));
  return apiFetch<WikipediaSearchResponse>(`/api/wikipedia/search?${query.toString()}`, {
    cache: "no-store",
  });
}

