import { apiFetch, apiPatchJson, apiPostJson } from "@/lib/api/client";
import { apiRoutes } from "@/lib/api/routes";

// --------------- Types ---------------

export type ApiZettelCard = {
  id: number;
  title: string;
  content: string | null;
  summary: string | null;
  tags: string[] | null;
  topic: string | null;
  source_url: string | null;
  document_id: string | null;
  importance: number;
  confidence: number;
  status: string;
  created_at: string;
  updated_at: string;
};

export type ZettelCardCreatePayload = {
  title: string;
  content?: string;
  summary?: string;
  tags?: string[];
  topic?: string;
  source_url?: string;
  importance?: number;
  confidence?: number;
};

export type ZettelCardUpdatePayload = {
  title?: string;
  content?: string;
  summary?: string;
  tags?: string[];
  topic?: string;
  source_url?: string;
  importance?: number;
  confidence?: number;
  status?: string;
};

export type ZettelLinkCreatePayload = {
  to_card_id: number;
  type?: string;
  context?: string;
  bidirectional?: boolean;
};

export type ApiZettelLink = {
  id: number;
  from_card_id: number;
  to_card_id: number;
  type: string;
  context: string | null;
  bidirectional: boolean;
  created_at: string;
  updated_at: string;
};

export type LinkSuggestion = {
  to_card_id: number;
  to_title: string;
  to_topic: string | null;
  to_tags: string[] | null;
  reason: string;
  scores: {
    semantic_score: number;
    tag_overlap: number;
    topic_match: boolean;
    citation_overlap: number;
    temporal_proximity_days: number | null;
    composite_score: number;
    confidence: string;
  };
};

export type AIGeneratePayload = {
  prompt?: string;
  content?: string;
  topic?: string;
  tags?: string[];
};

// --------------- Filter Types ---------------

export type ZettelFilterParams = {
  q?: string;
  topic?: string;
  tags?: string[];
  sort_by?: string;
  sort_dir?: string;
  importance_min?: number;
  status?: string;
  page?: number;
  pageSize?: number;
};

// --------------- Card Search (wiki-link autocomplete) ---------------

export type ZettelSearchResult = {
  id: number;
  title: string;
  topic: string | null;
  tags: string[];
  status: string;
};

export async function searchZettelCards(q: string, limit = 10): Promise<ZettelSearchResult[]> {
  if (!q.trim()) return [];
  const query = new URLSearchParams({ q: q.trim(), limit: String(limit) });
  return apiFetch<ZettelSearchResult[]>(`${apiRoutes.zettels.cards}/search?${query}`, { cache: "no-store" });
}

// --------------- Card CRUD ---------------

const DEFAULT_PAGE_SIZE = 24;

export async function listZettelCards(filters?: ZettelFilterParams): Promise<ApiZettelCard[]> {
  const query = new URLSearchParams();
  if (filters?.q) query.set("q", filters.q);
  if (filters?.topic) query.set("topic", filters.topic);
  if (filters?.tags && filters.tags.length > 0) {
    for (const tag of filters.tags) {
      query.append("tags", tag);
    }
  }
  if (filters?.sort_by) query.set("sort_by", filters.sort_by);
  if (filters?.sort_dir) query.set("sort_dir", filters.sort_dir);
  if (filters?.importance_min !== undefined) query.set("importance_min", String(filters.importance_min));
  if (filters?.status) {
    query.set("status", filters.status);
  } else {
    query.set("status", "");
  }
  const pageSize = filters?.pageSize ?? DEFAULT_PAGE_SIZE;
  const page = filters?.page ?? 0;
  query.set("limit", String(pageSize));
  query.set("skip", String(page * pageSize));

  const qs = query.toString();
  const url = qs ? `${apiRoutes.zettels.cards}?${qs}` : apiRoutes.zettels.cards;
  return apiFetch<ApiZettelCard[]>(url, { cache: "no-store" });
}

export async function countZettelCards(filters?: ZettelFilterParams): Promise<number> {
  const query = new URLSearchParams();
  if (filters?.q) query.set("q", filters.q);
  if (filters?.topic) query.set("topic", filters.topic);
  if (filters?.tags && filters.tags.length > 0) {
    for (const tag of filters.tags) query.append("tags", tag);
  }
  if (filters?.importance_min !== undefined) query.set("importance_min", String(filters.importance_min));
  if (filters?.status) {
    query.set("status", filters.status);
  } else {
    query.set("status", "");
  }
  const qs = query.toString();
  const url = qs ? `${apiRoutes.zettels.cards}/count?${qs}` : `${apiRoutes.zettels.cards}/count`;
  const res = await apiFetch<{ total: number }>(url, { cache: "no-store" });
  return res.total;
}

export async function listZettelsByDocument(documentId: string): Promise<ApiZettelCard[]> {
  const url = `${apiRoutes.zettels.cards}?document_id=${encodeURIComponent(documentId)}`;
  return apiFetch<ApiZettelCard[]>(url, { cache: "no-store" });
}

export async function getZettelCard(id: number): Promise<ApiZettelCard> {
  return apiFetch<ApiZettelCard>(apiRoutes.zettels.cardById(id));
}

export async function createZettelCard(payload: ZettelCardCreatePayload): Promise<ApiZettelCard> {
  return apiPostJson<ApiZettelCard, ZettelCardCreatePayload>(apiRoutes.zettels.cards, payload);
}

export async function updateZettelCard(id: number, payload: ZettelCardUpdatePayload): Promise<ApiZettelCard> {
  return apiPatchJson<ApiZettelCard, ZettelCardUpdatePayload>(apiRoutes.zettels.cardById(id), payload);
}

export async function deleteZettelCard(id: number): Promise<{ status: string; id: number }> {
  return apiFetch<{ status: string; id: number }>(apiRoutes.zettels.cardById(id), { method: "DELETE" });
}

// --------------- Links ---------------

export async function listZettelLinks(cardId: number): Promise<ApiZettelLink[]> {
  return apiFetch<ApiZettelLink[]>(apiRoutes.zettels.cardLinks(cardId));
}

export async function createZettelLink(cardId: number, payload: ZettelLinkCreatePayload): Promise<ApiZettelLink[]> {
  return apiPostJson<ApiZettelLink[], ZettelLinkCreatePayload>(apiRoutes.zettels.cardLinks(cardId), payload);
}

export async function deleteZettelLink(linkId: number): Promise<{ status: string; id: number }> {
  return apiFetch<{ status: string; id: number }>(apiRoutes.zettels.deleteLink(linkId), { method: "DELETE" });
}

export async function suggestZettelLinks(
  cardId: number,
  params?: { min_confidence?: number; limit?: number },
): Promise<LinkSuggestion[]> {
  const query = new URLSearchParams();
  if (params?.min_confidence !== undefined) query.set("min_confidence", String(params.min_confidence));
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  const qs = query.toString();
  const url = qs ? `${apiRoutes.zettels.suggestLinks(cardId)}?${qs}` : apiRoutes.zettels.suggestLinks(cardId);
  return apiPostJson<LinkSuggestion[], Record<string, never>>(url, {});
}

// --------------- Bulk Create ---------------

export async function bulkCreateZettelCards(
  payload: ZettelCardCreatePayload[]
): Promise<ApiZettelCard[]> {
  return apiPostJson<ApiZettelCard[], ZettelCardCreatePayload[]>(
    `${apiRoutes.zettels.cards}/bulk`, payload
  );
}

// --------------- AI Generation ---------------

export async function generateZettelCard(payload: AIGeneratePayload): Promise<ApiZettelCard> {
  return apiPostJson<ApiZettelCard, AIGeneratePayload>(apiRoutes.zettels.generate, payload);
}

// --------------- Facets (topics / tags) ---------------

export async function listZettelTopics(): Promise<string[]> {
  return apiFetch<string[]>(apiRoutes.zettels.topics, { cache: "no-store" });
}

export async function listZettelTags(): Promise<string[]> {
  return apiFetch<string[]>(apiRoutes.zettels.tags, { cache: "no-store" });
}
