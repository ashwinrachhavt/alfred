import type { QueryClient } from "@tanstack/react-query";

import { zettelCardsQueryOptions } from "@/features/zettels/queries";
import { workspacesQueryOptions } from "@/features/notes/queries";
import { explorerDocumentsQueryOptions } from "@/features/documents/queries";

type Prefetcher = (qc: QueryClient) => void;

const routePrefetchMap: Record<string, Prefetcher> = {
  "/knowledge": (qc) => qc.prefetchQuery(zettelCardsQueryOptions(qc)),
  "/notes": (qc) => qc.prefetchQuery(workspacesQueryOptions()),
  "/documents": (qc) => qc.prefetchInfiniteQuery(explorerDocumentsQueryOptions()),
};

export function prefetchRouteData(href: string, queryClient: QueryClient): void {
  const prefetcher = routePrefetchMap[href];
  if (prefetcher) {
    prefetcher(queryClient);
  }
}
