import { ApiError, apiFetch, apiPatchJson, apiPostJson } from "@/lib/api/client";
import { apiRoutes } from "@/lib/api/routes";
import type {
  DailyEntriesResponse,
  DailyEntryCreate,
  DailyEntryItem,
  DailyEntryUpdate,
  DailyReflection,
  ListTodayEntriesParams,
  RunTodayPipelineBody,
  RunTodayPipelineResponse,
} from "@/features/today/types";

export type TodayCaptureItem = {
  id: string;
  title: string;
  source_url: string | null;
  pipeline_status: string;
  content_type: string | null;
  created_at: string | null;
};

export type TodayStoredCardItem = {
  card_id: number;
  title: string;
  topic: string | null;
  status: string;
  tags: string[];
  created_at: string | null;
};

export type TodayConnectionItem = {
  link_id: number;
  from_card_id: number;
  from_title: string;
  to_card_id: number;
  to_title: string;
  type: string;
  created_at: string | null;
};

export type TodayReviewItem = {
  review_id: number;
  card_id: number;
  card_title: string;
  stage: number;
  due_at: string | null;
  completed_at: string | null;
  status: string;
};

export type TodayGapItem = {
  card_id: number;
  title: string;
  created_at: string | null;
};

export type TodayNoteItem = {
  note_id: string;
  title: string;
  icon: string | null;
  workspace_id: string;
  updated_at: string | null;
};

export type TodayBriefingStats = {
  total_captures: number;
  total_cards_created: number;
  total_connections: number;
  total_reviews_due: number;
  total_reviews_completed: number;
  total_gaps: number;
  total_events: number;
  total_cards: number;
  total_links: number;
  total_notes_touched: number;
};

export type TodayBriefingResponse = {
  date: string;
  timezone: string;
  generated_at: string;
  captures: TodayCaptureItem[];
  stored_cards: TodayStoredCardItem[];
  connections: TodayConnectionItem[];
  reviews: TodayReviewItem[];
  gaps: TodayGapItem[];
  notes: TodayNoteItem[];
  stats: TodayBriefingStats;
};

export type TodayCalendarDay = {
  date: string;
  captures: number;
  stored_cards: number;
  connections: number;
  reviews_due: number;
  reviews_completed: number;
  gaps: number;
  total_events: number;
};

export type TodayCalendarResponse = {
  start_date: string;
  end_date: string;
  timezone: string;
  days: TodayCalendarDay[];
};

type TodayBriefingParams = {
  date?: string;
  tz?: string;
};

type TodayCalendarParams = {
  start_date?: string;
  end_date?: string;
  days?: number;
  tz?: string;
};

function buildQuery(params: Record<string, string | number | undefined>): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined) continue;
    query.set(key, String(value));
  }
  return query.toString();
}

export async function getTodayBriefing(
  params: TodayBriefingParams = {},
): Promise<TodayBriefingResponse> {
  const query = buildQuery(params);
  const url = query ? `${apiRoutes.today.briefing}?${query}` : apiRoutes.today.briefing;
  return apiFetch<TodayBriefingResponse>(url, { cache: "no-store" });
}

export async function getTodayCalendar(
  params: TodayCalendarParams = {},
): Promise<TodayCalendarResponse> {
  const query = buildQuery(params);
  const url = query ? `${apiRoutes.today.calendar}?${query}` : apiRoutes.today.calendar;
  return apiFetch<TodayCalendarResponse>(url, { cache: "no-store" });
}

// ---------------------------------------------------------------------------
// DailyEntry CRUD — ``/api/today/entries`` (T3/T4)
// ---------------------------------------------------------------------------

function appendRepeated(
  query: URLSearchParams,
  key: string,
  values: readonly string[] | undefined,
): void {
  if (!values || values.length === 0) return;
  for (const value of values) {
    if (value === undefined || value === null) continue;
    query.append(key, String(value));
  }
}

function buildListEntriesQuery(params: ListTodayEntriesParams): string {
  const query = new URLSearchParams();
  query.set("start", params.start);
  query.set("end", params.end);
  if (params.tz) query.set("tz", params.tz);
  if (params.q) query.set("q", params.q);
  if (typeof params.include_artifacts === "boolean") {
    query.set("include_artifacts", params.include_artifacts ? "true" : "false");
  }
  if (typeof params.limit === "number") query.set("limit", String(params.limit));
  if (params.cursor) query.set("cursor", params.cursor);

  appendRepeated(query, "kind", params.kind);
  appendRepeated(query, "status", params.status);
  appendRepeated(query, "tag", params.tag);

  return query.toString();
}

export async function listTodayEntries(
  params: ListTodayEntriesParams,
): Promise<DailyEntriesResponse> {
  const query = buildListEntriesQuery(params);
  const url = query ? `${apiRoutes.today.entries}?${query}` : apiRoutes.today.entries;
  return apiFetch<DailyEntriesResponse>(url, { cache: "no-store" });
}

export async function createTodayEntry(body: DailyEntryCreate): Promise<DailyEntryItem> {
  return apiPostJson<DailyEntryItem, DailyEntryCreate>(apiRoutes.today.entries, body);
}

export async function updateTodayEntry(
  entryId: number,
  patch: DailyEntryUpdate,
): Promise<DailyEntryItem> {
  return apiPatchJson<DailyEntryItem, DailyEntryUpdate>(
    apiRoutes.today.entryById(entryId),
    patch,
  );
}

export async function deleteTodayEntry(entryId: number): Promise<void> {
  await apiFetch<unknown>(apiRoutes.today.entryById(entryId), { method: "DELETE" });
}

// ---------------------------------------------------------------------------
// Daily reflection + manual pipeline trigger (T12)
// ---------------------------------------------------------------------------

/**
 * Fetch the digest for a given date. Returns ``null`` for 404 (no
 * reflection yet) because the UI renders nothing in that case rather
 * than showing an error.
 */
export async function getTodayReflection(
  date: string,
  tz?: string,
): Promise<DailyReflection | null> {
  const base = apiRoutes.today.reflectionByDate(date);
  const url = tz ? `${base}?tz=${encodeURIComponent(tz)}` : base;
  try {
    return await apiFetch<DailyReflection>(url, { cache: "no-store" });
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return null;
    }
    throw error;
  }
}

export async function runTodayPipeline(
  body: RunTodayPipelineBody,
): Promise<RunTodayPipelineResponse> {
  return apiPostJson<RunTodayPipelineResponse, RunTodayPipelineBody>(
    apiRoutes.today.pipelineRun,
    body,
  );
}
