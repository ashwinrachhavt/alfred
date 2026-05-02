/**
 * Zettel Workspace API client (T10).
 *
 * Mirrors the Pydantic shapes from apps/alfred/schemas/zettel.py so the
 * frontend can stay typed without reaching into the backend.
 */
import { apiFetch, apiPostJson } from "@/lib/api/client";
import { apiRoutes } from "@/lib/api/routes";

// --------------- Types mirroring backend schemas ---------------

export type ZettelSessionStatus = "active" | "ended" | "abandoned";

export type ZettelSessionOut = {
  id: number;
  title: string | null;
  shared_topic: string | null;
  shared_tags: string[] | null;
  source_context: string | null;
  ended_at: string | null;
  summary: string | null;
  card_count: number;
  summary_card_id: number | null;
  status: ZettelSessionStatus | string;
  created_at: string | null;
  updated_at: string | null;
};

export type ZettelCardOut = {
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
  created_at: string | null;
  updated_at: string | null;
  // Bloom metadata (optional on legacy rows).
  bloom_level?: number | null;
  bloom_source?: string | null;
  enrichment_last_error?: string | null;
};

export type ZettelCardStub = {
  id: number;
  title: string;
  bloom_level: number;
  created_at: string | null;
  updated_at: string | null;
  is_archived: boolean;
};

export type HydrateResponse = {
  session: ZettelSessionOut;
  full_cards: ZettelCardOut[];
  stub_cards: ZettelCardStub[];
};

export type CreateSessionBody = {
  title?: string;
  shared_topic?: string;
  shared_tags?: string[];
  source_context?: string;
};

export type BulkFromDecompositionCandidate = {
  title: string;
  content: string;
  bloom_level: number;
  tags?: string[];
  /** Indexes within THIS request's candidates array (sibling links). */
  links_to_siblings?: number[];
};

export type BulkFromDecompositionBody = {
  session_id?: number | null;
  shared_topic?: string | null;
  source_url?: string | null;
  candidates: BulkFromDecompositionCandidate[];
};

export type BulkFromDecompositionResult = {
  created_card_ids: number[];
  link_count: number;
};

export type ResumeEnrichmentResult = {
  status: string;
  // Additional fields (suggested_title, summary, …) depending on server state.
  [k: string]: unknown;
};

// --------------- API calls ---------------

export async function createSession(
  body: CreateSessionBody = {},
): Promise<ZettelSessionOut> {
  return apiPostJson<ZettelSessionOut, CreateSessionBody>(
    apiRoutes.zettels.sessions.create,
    body,
  );
}

export async function endSession(
  sessionId: number,
): Promise<ZettelSessionOut> {
  return apiPostJson<ZettelSessionOut, Record<string, never>>(
    apiRoutes.zettels.sessions.end(sessionId),
    {},
  );
}

export async function hydrateSession(
  sessionId: number,
): Promise<HydrateResponse> {
  return apiFetch<HydrateResponse>(
    apiRoutes.zettels.sessions.hydrate(sessionId),
    { cache: "no-store" },
  );
}

export async function resumeEnrichment(
  cardId: number,
): Promise<ResumeEnrichmentResult> {
  return apiPostJson<ResumeEnrichmentResult, Record<string, never>>(
    apiRoutes.zettels.resumeEnrichment(cardId),
    {},
  );
}

export async function bulkFromDecomposition(
  body: BulkFromDecompositionBody,
): Promise<BulkFromDecompositionResult> {
  return apiPostJson<BulkFromDecompositionResult, BulkFromDecompositionBody>(
    apiRoutes.zettels.bulkFromDecomposition,
    body,
  );
}
