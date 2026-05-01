import { addMonths, endOfMonth, format, startOfMonth, subMonths } from "date-fns";
import { useQuery } from "@tanstack/react-query";

import {
  getTodayBriefing,
  getTodayCalendar,
  getTodayReflection,
  listTodayEntries,
} from "@/lib/api/today";
import type {
  DailyEntriesResponse,
  DailyReflection,
  ListTodayEntriesParams,
} from "@/features/today/types";

export function toIsoDay(value: Date): string {
  return format(value, "yyyy-MM-dd");
}

export function useTodayBriefing(selectedDate: Date, timeZone: string) {
  const day = toIsoDay(selectedDate);

  return useQuery({
    enabled: Boolean(timeZone),
    queryKey: ["today", "briefing", day, timeZone],
    queryFn: () => getTodayBriefing({ date: day, tz: timeZone }),
    staleTime: 60_000,
  });
}

export function useTodayCalendar(month: Date, timeZone: string) {
  const startDate = toIsoDay(startOfMonth(subMonths(month, 1)));
  const endDate = toIsoDay(endOfMonth(addMonths(month, 1)));

  return useQuery({
    enabled: Boolean(timeZone),
    queryKey: ["today", "calendar", startDate, endDate, timeZone],
    queryFn: () =>
      getTodayCalendar({
        start_date: startDate,
        end_date: endDate,
        tz: timeZone,
      }),
    staleTime: 60_000,
  });
}

// ---------------------------------------------------------------------------
// DailyEntry CRUD (T4)
// ---------------------------------------------------------------------------

/**
 * Normalize list params into a stable query-key fragment.
 *
 * - Sorts array filters so reorderings don't invalidate the cache.
 * - Omits undefined / empty-array / empty-string fields so they don't appear
 *   as ``null`` noise in the key (which would split caches).
 */
export function normalizeTodayEntriesParams(
  params: ListTodayEntriesParams,
): Record<string, unknown> {
  const normalized: Record<string, unknown> = {
    start: params.start,
    end: params.end,
  };
  if (params.tz) normalized.tz = params.tz;
  if (params.q) normalized.q = params.q;
  if (typeof params.include_artifacts === "boolean") {
    normalized.include_artifacts = params.include_artifacts;
  }
  if (typeof params.limit === "number") normalized.limit = params.limit;
  if (params.cursor) normalized.cursor = params.cursor;
  if (params.kind && params.kind.length > 0) {
    normalized.kind = [...params.kind].sort();
  }
  if (params.status && params.status.length > 0) {
    normalized.status = [...params.status].sort();
  }
  if (params.tag && params.tag.length > 0) {
    normalized.tag = [...params.tag].sort();
  }
  return normalized;
}

export type UseTodayEntriesParams = ListTodayEntriesParams & {
  enabled?: boolean;
};

export function useTodayEntries(params: UseTodayEntriesParams) {
  const { enabled, ...listParams } = params;
  const normalized = normalizeTodayEntriesParams(listParams);

  return useQuery<DailyEntriesResponse>({
    enabled: enabled !== false && Boolean(listParams.start) && Boolean(listParams.end),
    queryKey: ["today", "entries", normalized],
    queryFn: () => listTodayEntries(listParams),
    staleTime: 30_000,
    placeholderData: (previous) => previous,
  });
}

// ---------------------------------------------------------------------------
// Reflection (T12)
// ---------------------------------------------------------------------------

/**
 * Fetch the digest for a specific ISO date. Returns ``null`` when no
 * reflection exists yet (swallowed 404 in the fetch fn). Query stays
 * idle until a date is provided.
 */
export function useTodayReflection(date: string | undefined, tz?: string) {
  return useQuery<DailyReflection | null>({
    enabled: Boolean(date),
    queryKey: ["today", "reflection", date ?? null, tz ?? null],
    queryFn: () => getTodayReflection(date as string, tz),
    staleTime: 60_000,
  });
}
