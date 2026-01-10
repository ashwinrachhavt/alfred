import { apiFetch, apiPatchJson, apiPostJson } from "@/lib/api/client";

import type {
  BulkUpdateResult,
  CompleteReviewRequest,
  GraphSummary,
  LinkSuggestion,
  ZettelCardCreate,
  ZettelCardOut,
  ZettelCardPatch,
  ZettelLinkCreate,
  ZettelLinkOut,
  ZettelReviewOut,
} from "@/lib/api/types/zettels";

export async function listZettelCards(params?: {
  q?: string | null;
  topic?: string | null;
  tag?: string | null;
  limit?: number;
  skip?: number;
}): Promise<ZettelCardOut[]> {
  const query = new URLSearchParams();
  if (params?.q) query.set("q", params.q);
  if (params?.topic) query.set("topic", params.topic);
  if (params?.tag) query.set("tag", params.tag);
  if (typeof params?.limit === "number") query.set("limit", String(params.limit));
  if (typeof params?.skip === "number") query.set("skip", String(params.skip));
  const qs = query.toString();
  return apiFetch<ZettelCardOut[]>(`/api/zettels/cards${qs ? `?${qs}` : ""}`, { cache: "no-store" });
}

export async function createZettelCard(body: ZettelCardCreate): Promise<ZettelCardOut> {
  return apiPostJson<ZettelCardOut, ZettelCardCreate>("/api/zettels/cards", body, { cache: "no-store" });
}

export async function bulkCreateZettelCards(body: ZettelCardCreate[]): Promise<Record<string, unknown>> {
  return apiPostJson<Record<string, unknown>, ZettelCardCreate[]>(
    "/api/zettels/cards/bulk",
    body,
    { cache: "no-store" },
  );
}

export async function bulkUpdateZettelCards(body: ZettelCardPatch[]): Promise<BulkUpdateResult> {
  return apiPatchJson<BulkUpdateResult, ZettelCardPatch[]>("/api/zettels/cards/bulk", body, {
    cache: "no-store",
  });
}

export async function getZettelCard(cardId: number): Promise<ZettelCardOut> {
  return apiFetch<ZettelCardOut>(`/api/zettels/cards/${cardId}`, { cache: "no-store" });
}

export async function listZettelLinks(cardId: number): Promise<ZettelLinkOut[]> {
  return apiFetch<ZettelLinkOut[]>(`/api/zettels/cards/${cardId}/links`, { cache: "no-store" });
}

export async function linkZettelCard(cardId: number, body: ZettelLinkCreate): Promise<ZettelLinkOut[]> {
  return apiPostJson<ZettelLinkOut[], ZettelLinkCreate>(`/api/zettels/cards/${cardId}/links`, body, {
    cache: "no-store",
  });
}

export async function suggestZettelLinks(
  cardId: number,
  body: Record<string, never>,
  params?: { min_confidence?: number; limit?: number },
): Promise<LinkSuggestion[]> {
  const query = new URLSearchParams();
  if (typeof params?.min_confidence === "number") query.set("min_confidence", String(params.min_confidence));
  if (typeof params?.limit === "number") query.set("limit", String(params.limit));
  const qs = query.toString();
  return apiPostJson<LinkSuggestion[], Record<string, never>>(
    `/api/zettels/cards/${cardId}/suggest-links${qs ? `?${qs}` : ""}`,
    body,
    { cache: "no-store" },
  );
}

export async function getZettelsGraph(): Promise<GraphSummary> {
  return apiFetch<GraphSummary>("/api/zettels/graph", { cache: "no-store" });
}

export async function listDueZettelReviews(limit = 50): Promise<ZettelReviewOut[]> {
  const query = new URLSearchParams();
  query.set("limit", String(limit));
  return apiFetch<ZettelReviewOut[]>(`/api/zettels/reviews/due?${query.toString()}`, { cache: "no-store" });
}

export async function completeZettelReview(
  reviewId: number,
  body: CompleteReviewRequest,
): Promise<ZettelReviewOut> {
  return apiPostJson<ZettelReviewOut, CompleteReviewRequest>(
    `/api/zettels/reviews/${reviewId}/complete`,
    body,
    { cache: "no-store" },
  );
}

