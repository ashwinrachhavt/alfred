import { useQuery } from "@tanstack/react-query";

import { getNotionHistory, type GetNotionHistoryParams } from "@/lib/api/notion";

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

