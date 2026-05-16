import type { QueryClient } from "@tanstack/react-query";

let streamingQueryClient: QueryClient | null = null;

export function bindStreamingQueryClient(queryClient: QueryClient | null): () => void {
  streamingQueryClient = queryClient;
  return () => {
    if (streamingQueryClient === queryClient) streamingQueryClient = null;
  };
}

export function notifyStreamCacheEvent(
  event: string,
  data: Record<string, unknown>,
): void {
  const queryClient = streamingQueryClient;
  if (!queryClient) return;

  if (isZettelInvalidationEvent(event, data)) {
    invalidateZettelQueries(queryClient);
  }

  if (event === "done" && typeof data.report_id === "string") {
    invalidateResearchReportQueries(queryClient, data.report_id);
  }
}

function isZettelInvalidationEvent(
  event: string,
  data: Record<string, unknown>,
): boolean {
  if (event === "card_saved" || event === "links_created" || event === "bloom_inferred") {
    return true;
  }
  if (event !== "artifact") return false;
  return data.type === "zettel" && (
    data.action === "created" ||
    data.action === "updated" ||
    data.action === "found"
  );
}

function invalidateZettelQueries(queryClient: QueryClient): void {
  void queryClient.invalidateQueries({ queryKey: ["zettels"] });
  void queryClient.invalidateQueries({ queryKey: ["zettel-topics"] });
  void queryClient.invalidateQueries({ queryKey: ["zettel-tags"] });
}

function invalidateResearchReportQueries(
  queryClient: QueryClient,
  reportId: string,
): void {
  void queryClient.invalidateQueries({ queryKey: ["research", "reports"] });
  void queryClient.invalidateQueries({
    queryKey: ["research", "reports", "by-id", reportId],
  });
}
