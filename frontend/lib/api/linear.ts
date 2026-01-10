import { apiFetch } from "@/lib/api/client";

import type { LinearIssuesResponse, LinearStatusResponse } from "@/lib/api/types/linear";

export type LinearStatusParams = {
  validate?: boolean;
};

export async function getLinearStatus(params: LinearStatusParams = {}): Promise<LinearStatusResponse> {
  const query = new URLSearchParams();
  if (params.validate) query.set("validate", "true");
  const qs = query.toString();
  return apiFetch<LinearStatusResponse>(`/api/linear/status${qs ? `?${qs}` : ""}`, {
    cache: "no-store",
  });
}

export type LinearIssuesParams = {
  start_date?: string | null;
  end_date?: string | null;
  include_comments?: boolean;
  limit?: number;
  format?: "raw" | "formatted" | "markdown";
};

export async function listLinearIssues(params: LinearIssuesParams): Promise<LinearIssuesResponse> {
  const query = new URLSearchParams();
  if (params.start_date) query.set("start_date", params.start_date);
  if (params.end_date) query.set("end_date", params.end_date);
  if (params.include_comments) query.set("include_comments", "true");
  if (typeof params.limit === "number") query.set("limit", String(params.limit));
  if (params.format) query.set("format", params.format);
  const qs = query.toString();
  return apiFetch<LinearIssuesResponse>(`/api/linear/issues${qs ? `?${qs}` : ""}`, {
    cache: "no-store",
  });
}

