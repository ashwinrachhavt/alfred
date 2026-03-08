import { apiFetch, apiPostJson } from "@/lib/api/client";
import type {
  NotionAuthUrlResponse,
  NotionHistoryResponse,
  NotionPageMarkdownResponse,
  NotionPageSearchResponse,
  NotionStatusResponse,
  UpdateNotionPageMarkdownRequest,
  UpdateNotionPageMarkdownResponse,
} from "@/lib/api/types/notion";

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

export async function searchNotionPages(params: {
  q: string;
  limit?: number;
}): Promise<NotionPageSearchResponse> {
  const query = new URLSearchParams();
  query.set("q", params.q);
  if (typeof params.limit === "number") query.set("limit", String(params.limit));
  return apiFetch(`/api/notion/search?${query.toString()}`);
}

export async function getNotionPageMarkdown(pageId: string): Promise<NotionPageMarkdownResponse> {
  return apiFetch(`/api/notion/pages/${encodeURIComponent(pageId)}/markdown`);
}

export async function updateNotionPageMarkdown(
  pageId: string,
  payload: UpdateNotionPageMarkdownRequest,
): Promise<UpdateNotionPageMarkdownResponse> {
  return apiPostJson(`/api/notion/pages/${encodeURIComponent(pageId)}/markdown`, payload);
}

export async function getNotionStatus(): Promise<NotionStatusResponse> {
  return apiFetch("/api/notion/status");
}

export async function getNotionAuthUrl(): Promise<NotionAuthUrlResponse> {
  return apiFetch("/api/notion/auth_url");
}

export async function revokeNotionWorkspace(workspaceId: string): Promise<{ ok: boolean }> {
  return apiPostJson("/api/notion/revoke", { workspace_id: workspaceId });
}
