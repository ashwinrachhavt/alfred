import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { Query } from "@tanstack/react-query";

import {
  createTodayEntry,
  deleteTodayEntry,
  runTodayPipeline,
  synthesizeTodayThread,
  updateTodayEntry,
} from "@/lib/api/today";
import type {
  DailyEntriesResponse,
  DailyEntryCreate,
  DailyEntryItem,
  DailyEntryUpdate,
  RunTodayPipelineBody,
  RunTodayPipelineResponse,
} from "@/features/today/types";
import type {
  TodayThreadSynthesisRequest,
  TodayThreadSynthesisResponse,
} from "@/lib/api/today";

const TODAY_ENTRIES_KEY = ["today", "entries"] as const;

type EntriesQueryData = DailyEntriesResponse;

type EntriesQuerySnapshot = {
  queryKey: readonly unknown[];
  data: EntriesQueryData;
};

function matchEntriesQuery(query: Query): boolean {
  const key = query.queryKey;
  return (
    Array.isArray(key) &&
    key.length >= 2 &&
    key[0] === "today" &&
    key[1] === "entries"
  );
}

function invalidateTodayEntries(
  queryClient: ReturnType<typeof useQueryClient>,
): Promise<void> {
  return queryClient.invalidateQueries({ queryKey: TODAY_ENTRIES_KEY });
}

/**
 * Create a daily entry and invalidate all ``["today", "entries", ...]``
 * caches on success.
 */
export function useCreateTodayEntry() {
  const queryClient = useQueryClient();

  return useMutation<DailyEntryItem, Error, DailyEntryCreate>({
    mutationFn: (payload: DailyEntryCreate) => createTodayEntry(payload),
    onSuccess: () => {
      void invalidateTodayEntries(queryClient);
    },
  });
}

/**
 * Partially update a daily entry with an optimistic cache update.
 *
 * Snapshots every matching ``["today", "entries", ...]`` query, applies the
 * patch in-place, and rolls back on error.
 */
export function useUpdateTodayEntry() {
  const queryClient = useQueryClient();

  return useMutation<
    DailyEntryItem,
    Error,
    { id: number; patch: DailyEntryUpdate },
    { snapshots: EntriesQuerySnapshot[] }
  >({
    mutationFn: ({ id, patch }) => updateTodayEntry(id, patch),
    onMutate: async ({ id, patch }) => {
      await queryClient.cancelQueries({ queryKey: TODAY_ENTRIES_KEY });

      const queries = queryClient
        .getQueryCache()
        .findAll({ predicate: matchEntriesQuery });

      const snapshots: EntriesQuerySnapshot[] = [];

      for (const query of queries) {
        const data = query.state.data as EntriesQueryData | undefined;
        if (!data) continue;
        const queryKey = query.queryKey;
        snapshots.push({ queryKey, data });

        const nextEntries = data.entries.map((entry) => {
          if (entry.id !== id) return entry;
          // Synthetic rows can't be patched — leave them alone.
          if (entry.is_synthetic) return entry;
          return {
            ...entry,
            ...patch,
            updated_at: new Date().toISOString(),
          } as DailyEntryItem;
        });

        queryClient.setQueryData<EntriesQueryData>(queryKey, {
          ...data,
          entries: nextEntries,
        });
      }

      return { snapshots };
    },
    onError: (_err, _vars, context) => {
      if (!context) return;
      for (const { queryKey, data } of context.snapshots) {
        queryClient.setQueryData(queryKey, data);
      }
    },
    onSettled: () => {
      void invalidateTodayEntries(queryClient);
    },
  });
}

/**
 * Delete a daily entry and invalidate all ``["today", "entries", ...]``
 * caches on success.
 */
export function useDeleteTodayEntry() {
  const queryClient = useQueryClient();

  return useMutation<void, Error, number>({
    mutationFn: (id: number) => deleteTodayEntry(id),
    onSuccess: () => {
      void invalidateTodayEntries(queryClient);
    },
  });
}

// ---------------------------------------------------------------------------
// Manual pipeline trigger (T12)
// ---------------------------------------------------------------------------

/**
 * Run or enqueue the Today pipeline. On success, invalidates both the
 * reflection cache (so the new digest shows up) and the entries cache
 * (so carry-over'd todos surface on today's views).
 */
export function useRunTodayPipeline() {
  const queryClient = useQueryClient();

  return useMutation<RunTodayPipelineResponse, Error, RunTodayPipelineBody>({
    mutationFn: (body: RunTodayPipelineBody) => runTodayPipeline(body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["today", "reflection"] });
      void invalidateTodayEntries(queryClient);
    },
  });
}

export function useSynthesizeTodayThread() {
  const queryClient = useQueryClient();

  return useMutation<TodayThreadSynthesisResponse, Error, TodayThreadSynthesisRequest>({
    mutationFn: (body: TodayThreadSynthesisRequest) => synthesizeTodayThread(body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["today", "briefing"] });
      void queryClient.invalidateQueries({ queryKey: ["today", "calendar"] });
      void queryClient.invalidateQueries({ queryKey: ["zettels"] });
      void queryClient.invalidateQueries({ queryKey: ["zettel-graph-extended"] });
    },
  });
}
