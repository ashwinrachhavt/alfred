import { apiFetch } from "@/lib/api/client";
import type { NotionHistoryResponse } from "@/lib/api/types/notion";

export type GetNotionHistoryParams = {
  start_date?: string | null;
  end_date?: string | null;
  limit?: number;
  include_content?: boolean;
};

function buildQuery(params: GetNotionHistoryParams): string {
  const q = new URLSearchParams();
  if (params.start_date) q.set("start_date", params.start_date);
  if (params.end_date) q.set("end_date", params.end_date);
  if (typeof params.limit === "number") q.set("limit", String(params.limit));
  if (typeof params.include_content === "boolean") {
    q.set("include_content", params.include_content ? "true" : "false");
  }
  const s = q.toString();
  return s ? `?${s}` : "";
}

export async function getNotionHistory(
  params: GetNotionHistoryParams = {},
): Promise<NotionHistoryResponse> {
  return apiFetch(`/api/notion/history${buildQuery(params)}`);
}

