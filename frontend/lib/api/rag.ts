import { apiFetch } from "@/lib/api/client";

import type { RagAnswerMode, RagAnswerResponse } from "@/lib/api/types/rag";

export type RagAnswerParams = {
  q: string;
  k?: number;
  include_context?: boolean;
  mode?: RagAnswerMode;
};

export async function ragAnswer(params: RagAnswerParams): Promise<RagAnswerResponse> {
  const query = new URLSearchParams();
  query.set("q", params.q);
  if (typeof params.k === "number") query.set("k", String(params.k));
  if (params.include_context) query.set("include_context", "true");
  if (params.mode) query.set("mode", params.mode);
  return apiFetch<RagAnswerResponse>(`/api/rag/answer?${query.toString()}`, { cache: "no-store" });
}

