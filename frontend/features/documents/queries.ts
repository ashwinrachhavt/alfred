import { useInfiniteQuery, useQuery } from "@tanstack/react-query";

import { getDocumentDetails, getSemanticMap, listExplorerDocuments } from "@/lib/api/documents";

export function explorerDocumentsQueryKey(params: {
  limit: number;
  filterTopic: string;
  search: string;
}) {
  return ["documents", "explorer", params.limit, params.filterTopic, params.search] as const;
}

export function semanticMapQueryKey(limit: number) {
  return ["documents", "semantic-map", limit] as const;
}

export function documentDetailsQueryKey(docId: string) {
  return ["documents", "details", docId] as const;
}

export function useExplorerDocuments(params: { limit?: number; filterTopic?: string; search?: string } = {}) {
  const limit = Math.max(1, Math.min(200, params.limit ?? 24));
  const filterTopic = (params.filterTopic ?? "").trim();
  const search = (params.search ?? "").trim();

  return useInfiniteQuery({
    queryKey: explorerDocumentsQueryKey({ limit, filterTopic, search }),
    initialPageParam: null as string | null,
    queryFn: ({ pageParam }) =>
      listExplorerDocuments({
        limit,
        cursor: pageParam,
        filter_topic: filterTopic || null,
        search: search || null,
      }),
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
    staleTime: 10_000,
  });
}

export function useSemanticMap(params: { limit?: number; enabled?: boolean } = {}) {
  const limit = Math.max(1, Math.min(20_000, params.limit ?? 5000));

  return useQuery({
    enabled: params.enabled ?? true,
    queryKey: semanticMapQueryKey(limit),
    queryFn: () => getSemanticMap({ limit }),
    staleTime: 10 * 60 * 1000,
  });
}

export function useDocumentDetails(docId: string | null) {
  return useQuery({
    enabled: Boolean(docId),
    queryKey: docId ? documentDetailsQueryKey(docId) : ["documents", "details", "disabled"],
    queryFn: () => getDocumentDetails(docId!),
    staleTime: 0,
  });
}

