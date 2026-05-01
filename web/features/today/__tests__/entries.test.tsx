import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import React from "react";
import { renderHook, waitFor, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { normalizeTodayEntriesParams, useTodayEntries } from "@/features/today/queries";
import {
  useCreateTodayEntry,
  useDeleteTodayEntry,
  useUpdateTodayEntry,
} from "@/features/today/mutations";
import type {
  DailyEntriesResponse,
  DailyEntryItem,
} from "@/features/today/types";

// --- Module-level mock of the fetch layer --------------------------------

vi.mock("@/lib/api/today", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/today")>(
    "@/lib/api/today",
  );
  return {
    ...actual,
    listTodayEntries: vi.fn(),
    createTodayEntry: vi.fn(),
    updateTodayEntry: vi.fn(),
    deleteTodayEntry: vi.fn(),
  };
});

// Import after mock so we reference the mocked fns.
import {
  createTodayEntry,
  deleteTodayEntry,
  listTodayEntries,
  updateTodayEntry,
} from "@/lib/api/today";

const mockedList = vi.mocked(listTodayEntries);
const mockedCreate = vi.mocked(createTodayEntry);
const mockedUpdate = vi.mocked(updateTodayEntry);
const mockedDelete = vi.mocked(deleteTodayEntry);

// --- Helpers -------------------------------------------------------------

function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: 0 },
      mutations: { retry: false },
    },
  });
}

function wrapperFor(client: QueryClient) {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(QueryClientProvider, { client, children });
  };
}

function makeEntry(partial: Partial<DailyEntryItem>): DailyEntryItem {
  return {
    id: 1,
    kind: "todo",
    entry_date: "2026-04-30",
    title: "Example",
    body_md: "",
    status: "open",
    priority: 0,
    tags: [],
    meta: {},
    created_at: "2026-04-30T00:00:00Z",
    updated_at: "2026-04-30T00:00:00Z",
    is_synthetic: false,
    ...partial,
  };
}

function makeResponse(entries: DailyEntryItem[]): DailyEntriesResponse {
  return { entries, next_cursor: null, total: entries.length };
}

// -------------------------------------------------------------------------

beforeEach(() => {
  mockedList.mockReset();
  mockedCreate.mockReset();
  mockedUpdate.mockReset();
  mockedDelete.mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

// =========================================================================
// normalizeTodayEntriesParams
// =========================================================================

describe("normalizeTodayEntriesParams", () => {
  it("omits undefined and empty arrays so the key stays stable", () => {
    const result = normalizeTodayEntriesParams({
      start: "2026-04-01",
      end: "2026-04-30",
      kind: [],
      tag: undefined,
    });
    expect(result).toEqual({ start: "2026-04-01", end: "2026-04-30" });
  });

  it("sorts filter arrays so reorderings don't split the cache", () => {
    const a = normalizeTodayEntriesParams({
      start: "2026-04-01",
      end: "2026-04-30",
      kind: ["note", "todo"],
      status: ["done", "open"],
      tag: ["b", "a"],
    });
    const b = normalizeTodayEntriesParams({
      start: "2026-04-01",
      end: "2026-04-30",
      kind: ["todo", "note"],
      status: ["open", "done"],
      tag: ["a", "b"],
    });
    expect(a).toEqual(b);
    expect(a.kind).toEqual(["note", "todo"]);
  });
});

// =========================================================================
// useTodayEntries
// =========================================================================

describe("useTodayEntries", () => {
  it("calls listTodayEntries with the right params and surfaces the response", async () => {
    const response = makeResponse([makeEntry({ id: 7, title: "Write T4" })]);
    mockedList.mockResolvedValueOnce(response);

    const client = makeQueryClient();
    const { result } = renderHook(
      () =>
        useTodayEntries({
          start: "2026-04-01",
          end: "2026-04-30",
          tz: "America/Los_Angeles",
          kind: ["todo"],
          status: ["open"],
          include_artifacts: true,
        }),
      { wrapper: wrapperFor(client) },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockedList).toHaveBeenCalledTimes(1);
    expect(mockedList).toHaveBeenCalledWith({
      start: "2026-04-01",
      end: "2026-04-30",
      tz: "America/Los_Angeles",
      kind: ["todo"],
      status: ["open"],
      include_artifacts: true,
    });
    expect(result.current.data).toEqual(response);
  });

  it("stays disabled when start/end are missing", () => {
    const client = makeQueryClient();
    const { result } = renderHook(
      () => useTodayEntries({ start: "", end: "" }),
      { wrapper: wrapperFor(client) },
    );
    expect(mockedList).not.toHaveBeenCalled();
    expect(result.current.fetchStatus).toBe("idle");
  });
});

// =========================================================================
// useCreateTodayEntry
// =========================================================================

describe("useCreateTodayEntry", () => {
  it("invalidates ['today','entries'] on success", async () => {
    mockedCreate.mockResolvedValueOnce(makeEntry({ id: 10, title: "New" }));

    const client = makeQueryClient();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useCreateTodayEntry(), {
      wrapper: wrapperFor(client),
    });

    await act(async () => {
      await result.current.mutateAsync({
        entry_date: "2026-04-30",
        kind: "todo",
        title: "New",
      });
    });

    expect(mockedCreate).toHaveBeenCalledWith({
      entry_date: "2026-04-30",
      kind: "todo",
      title: "New",
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: ["today", "entries"],
    });
  });
});

// =========================================================================
// useUpdateTodayEntry — optimistic update
// =========================================================================

describe("useUpdateTodayEntry", () => {
  it("optimistically patches the entry in the cache then persists", async () => {
    const existing = makeEntry({ id: 42, title: "Old", status: "open" });
    const queryKey = [
      "today",
      "entries",
      { start: "2026-04-01", end: "2026-04-30" },
    ];

    const client = makeQueryClient();
    client.setQueryData<DailyEntriesResponse>(queryKey, makeResponse([existing]));

    // Delay resolution so we can observe the optimistic state first.
    let resolveFn: ((value: DailyEntryItem) => void) | null = null;
    mockedUpdate.mockImplementationOnce(
      () =>
        new Promise<DailyEntryItem>((resolve) => {
          resolveFn = resolve;
        }),
    );

    const { result } = renderHook(() => useUpdateTodayEntry(), {
      wrapper: wrapperFor(client),
    });

    let pending: Promise<DailyEntryItem>;
    act(() => {
      pending = result.current.mutateAsync({
        id: 42,
        patch: { status: "done", title: "New" },
      });
    });

    // After onMutate, the cache should already reflect the patch.
    await waitFor(() => {
      const cached = client.getQueryData<DailyEntriesResponse>(queryKey);
      expect(cached?.entries[0].status).toBe("done");
      expect(cached?.entries[0].title).toBe("New");
    });

    // Resolve the backend call.
    act(() => {
      resolveFn!(makeEntry({ id: 42, title: "New", status: "done" }));
    });

    await act(async () => {
      await pending!;
    });

    // Still reflects the patch after settle.
    const final = client.getQueryData<DailyEntriesResponse>(queryKey);
    expect(final?.entries[0].status).toBe("done");
    expect(final?.entries[0].title).toBe("New");
  });

  it("rolls back to the snapshot when the request fails", async () => {
    const existing = makeEntry({ id: 42, title: "Old", status: "open" });
    const queryKey = [
      "today",
      "entries",
      { start: "2026-04-01", end: "2026-04-30" },
    ];

    const client = makeQueryClient();
    client.setQueryData<DailyEntriesResponse>(queryKey, makeResponse([existing]));

    mockedUpdate.mockRejectedValueOnce(new Error("nope"));

    const { result } = renderHook(() => useUpdateTodayEntry(), {
      wrapper: wrapperFor(client),
    });

    await act(async () => {
      await expect(
        result.current.mutateAsync({
          id: 42,
          patch: { status: "done" },
        }),
      ).rejects.toThrow("nope");
    });

    const final = client.getQueryData<DailyEntriesResponse>(queryKey);
    expect(final?.entries[0].status).toBe("open");
    expect(final?.entries[0].title).toBe("Old");
  });
});

// =========================================================================
// useDeleteTodayEntry
// =========================================================================

describe("useDeleteTodayEntry", () => {
  it("invalidates ['today','entries'] on success", async () => {
    mockedDelete.mockResolvedValueOnce(undefined);

    const client = makeQueryClient();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useDeleteTodayEntry(), {
      wrapper: wrapperFor(client),
    });

    await act(async () => {
      await result.current.mutateAsync(99);
    });

    expect(mockedDelete).toHaveBeenCalledWith(99);
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: ["today", "entries"],
    });
  });
});
