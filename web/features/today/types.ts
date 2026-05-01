/**
 * TypeScript types mirroring the Pydantic schemas in
 * ``apps/alfred/schemas/today.py`` for the DailyEntry CRUD surface (T3).
 *
 * Keep this file in sync with the backend schemas.
 */

export type TodayEntryKind = "todo" | "note" | "learning" | "artifact_ref";

export type TodayEntryStatus = "open" | "doing" | "done" | "skipped";

/**
 * Single entry as returned by ``GET /api/today/entries``.
 *
 * ``id`` is ``number`` for real rows and ``string`` (e.g. ``"zettel:123"``)
 * for synthetic ``artifact_ref`` rows derived from zettels/captures/reviews.
 */
export interface DailyEntryItem {
  id: number | string;
  kind: TodayEntryKind;
  entry_date: string; // ISO date (YYYY-MM-DD)
  title: string;
  body_md: string;
  status: string | null; // null for artifact_ref rows
  priority: number;
  tags: string[];
  meta: Record<string, unknown>;
  created_at: string | null;
  updated_at: string | null;
  is_synthetic: boolean;
}

export interface DailyEntryCreate {
  entry_date: string; // ISO date (YYYY-MM-DD)
  kind: Exclude<TodayEntryKind, "artifact_ref">;
  title: string;
  body_md?: string;
  status?: TodayEntryStatus;
  priority?: number;
  tags?: string[];
  meta?: Record<string, unknown>;
  user_id?: string | null;
}

export interface DailyEntryUpdate {
  kind?: Exclude<TodayEntryKind, "artifact_ref">;
  title?: string;
  body_md?: string;
  status?: TodayEntryStatus;
  priority?: number;
  tags?: string[];
  meta?: Record<string, unknown>;
  entry_date?: string; // ISO date (YYYY-MM-DD)
}

export interface DailyEntriesResponse {
  entries: DailyEntryItem[];
  next_cursor: string | null;
  total: number;
}

export interface ListTodayEntriesParams {
  start: string; // ISO date
  end: string; // ISO date
  tz?: string;
  kind?: string[];
  status?: string[];
  tag?: string[];
  q?: string;
  include_artifacts?: boolean;
  limit?: number;
  cursor?: string;
}
