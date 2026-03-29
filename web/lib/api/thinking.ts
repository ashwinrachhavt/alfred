import { apiFetch, apiPatchJson, apiPostJson } from "@/lib/api/client";
import { apiRoutes } from "@/lib/api/routes";
import type {
  DecomposeResponse,
  ThinkingSession,
  ThinkingSessionSummary,
} from "@/lib/api/types/thinking";

// ---------------------------------------------------------------------------
// List sessions
// ---------------------------------------------------------------------------

type ListSessionsParams = {
  status?: string;
  limit?: number;
  skip?: number;
};

export async function listThinkingSessions(
  params?: ListSessionsParams,
): Promise<ThinkingSessionSummary[]> {
  const query = new URLSearchParams();
  if (params?.status) query.set("status", params.status);
  if (params?.limit != null) query.set("limit", String(params.limit));
  if (params?.skip != null) query.set("skip", String(params.skip));
  const qs = query.toString();
  const url = qs
    ? `${apiRoutes.thinking.sessions}?${qs}`
    : apiRoutes.thinking.sessions;
  return apiFetch<ThinkingSessionSummary[]>(url, { cache: "no-store" });
}

// ---------------------------------------------------------------------------
// Get single session
// ---------------------------------------------------------------------------

export async function getThinkingSession(id: number): Promise<ThinkingSession> {
  return apiFetch<ThinkingSession>(apiRoutes.thinking.sessionById(id), {
    cache: "no-store",
  });
}

// ---------------------------------------------------------------------------
// Create session
// ---------------------------------------------------------------------------

type CreateSessionPayload = {
  title?: string | null;
  topic?: string | null;
  tags?: string[];
};

export async function createThinkingSession(
  data: CreateSessionPayload,
): Promise<ThinkingSession> {
  return apiPostJson<ThinkingSession, CreateSessionPayload>(
    apiRoutes.thinking.sessions,
    data,
  );
}

// ---------------------------------------------------------------------------
// Update session
// ---------------------------------------------------------------------------

type UpdateSessionPayload = {
  title?: string | null;
  blocks?: unknown[];
  tags?: string[];
  status?: "draft" | "published" | "archived";
  pinned?: boolean;
};

export async function updateThinkingSession(
  id: number,
  data: UpdateSessionPayload,
): Promise<ThinkingSession> {
  return apiPatchJson<ThinkingSession, UpdateSessionPayload>(
    apiRoutes.thinking.sessionById(id),
    data,
  );
}

// ---------------------------------------------------------------------------
// Archive session
// ---------------------------------------------------------------------------

export async function archiveThinkingSession(
  id: number,
): Promise<ThinkingSession> {
  return apiPatchJson<ThinkingSession, Record<string, never>>(
    apiRoutes.thinking.archive(id),
    {},
  );
}

// ---------------------------------------------------------------------------
// Fork session
// ---------------------------------------------------------------------------

export async function forkThinkingSession(
  id: number,
): Promise<ThinkingSession> {
  return apiPostJson<ThinkingSession, Record<string, never>>(
    apiRoutes.thinking.fork(id),
    {},
  );
}

// ---------------------------------------------------------------------------
// Decompose
// ---------------------------------------------------------------------------

type DecomposePayload = {
  topic?: string;
  url?: string;
  text?: string;
};

export async function decompose(
  data: DecomposePayload,
): Promise<DecomposeResponse> {
  return apiPostJson<DecomposeResponse, DecomposePayload>(
    apiRoutes.thinking.decompose,
    data,
  );
}
