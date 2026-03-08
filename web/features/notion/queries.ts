import { useQuery } from "@tanstack/react-query";

import { getNotionHistory, getNotionPageMarkdown, getNotionStatus, searchNotionPages, type GetNotionHistoryParams } from "@/lib/api/notion";

export function notionHistoryQueryKey(params: GetNotionHistoryParams) {
  return [
    "notion",
    "history",
    params.start_date ?? null,
    params.end_date ?? null,
    params.limit ?? null,
    params.include_content ?? false,
  ] as const;
}

export function useNotionHistory(params: GetNotionHistoryParams) {
  return useQuery({
    queryKey: notionHistoryQueryKey(params),
    queryFn: () => getNotionHistory(params),
    staleTime: 30_000,
  });
}

export function notionPageSearchQueryKey(params: { q: string; limit: number }) {
  return ["notion", "search", params.q, params.limit] as const;
}

export function useNotionPageSearch(params: { q: string; limit?: number; enabled?: boolean }) {
  const q = params.q.trim();
  const limit = Math.max(1, Math.min(50, params.limit ?? 20));

  return useQuery({
    enabled: (params.enabled ?? true) && q.length > 0,
    queryKey: notionPageSearchQueryKey({ q, limit }),
    queryFn: () => searchNotionPages({ q, limit }),
    staleTime: 15_000,
  });
}

export function useNotionStatus() {
  return useQuery({
    queryKey: ["notion", "status"],
    queryFn: getNotionStatus,
    staleTime: 10_000,
  });
}

export function notionPageMarkdownQueryKey(pageId: string) {
  return ["notion", "page", pageId, "markdown"] as const;
}

export function useNotionPageMarkdown(pageId: string | null) {
  return useQuery({
    enabled: Boolean(pageId),
    queryKey: pageId ? notionPageMarkdownQueryKey(pageId) : ["notion", "page", "disabled"],
    queryFn: () => getNotionPageMarkdown(pageId!),
    staleTime: 0,
  });
}
