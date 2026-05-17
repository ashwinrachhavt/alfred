import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { normalizeTaskListParams } from "@/features/task-system/queries";
import { useDeleteTaskSystemTask, useUpdateTaskSystemTask } from "@/features/task-system/mutations";
import type { TaskItem, TaskListResponse } from "@/features/task-system/types";

vi.mock("@/lib/api/task-system", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/task-system")>(
    "@/lib/api/task-system",
  );
  return {
    ...actual,
    updateTaskSystemTask: vi.fn(),
    deleteTaskSystemTask: vi.fn(),
  };
});

import { deleteTaskSystemTask, updateTaskSystemTask } from "@/lib/api/task-system";

const mockedUpdate = vi.mocked(updateTaskSystemTask);
const mockedDelete = vi.mocked(deleteTaskSystemTask);

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
    return React.createElement(QueryClientProvider, { client }, children);
  };
}

function makeTask(partial: Partial<TaskItem> = {}): TaskItem {
  return {
    id: 1,
    user_id: "user_1",
    board_id: 1,
    column_id: 2,
    project_id: null,
    title: "Task",
    description_md: "",
    priority: "MEDIUM",
    status: "TODO",
    type: null,
    estimate_minutes: null,
    estimated_pomodoros: null,
    completed_pomodoros: 0,
    story_points: null,
    due_at: null,
    due_date: null,
    tags: [],
    topics: [],
    primary_topic: null,
    source: null,
    source_kind: null,
    source_id: null,
    source_url: null,
    auto_generated: false,
    ai_planned: false,
    from_brain_dump: false,
    ai_state: "RAW",
    ai_confidence: null,
    ai_next_action: null,
    completed_at: null,
    meta: {},
    created_at: "2026-05-17T00:00:00Z",
    updated_at: "2026-05-17T00:00:00Z",
    ...partial,
  };
}

function makeResponse(tasks: TaskItem[]): TaskListResponse {
  return { tasks, total: tasks.length, next_cursor: null };
}

beforeEach(() => {
  mockedUpdate.mockReset();
  mockedDelete.mockReset();
});

describe("normalizeTaskListParams", () => {
  it("omits undefined and empty arrays", () => {
    expect(normalizeTaskListParams({ status: [], priority: [], limit: undefined })).toEqual({});
  });

  it("sorts repeated filters for stable query keys", () => {
    const a = normalizeTaskListParams({ status: ["DONE", "TODO"], priority: ["LOW", "HIGH"] });
    const b = normalizeTaskListParams({ status: ["TODO", "DONE"], priority: ["HIGH", "LOW"] });
    expect(a).toEqual(b);
    expect(a).toEqual({ priority: ["HIGH", "LOW"], status: ["DONE", "TODO"] });
  });
});

describe("task-system optimistic mutations", () => {
  it("rolls back an optimistic update when the request fails", async () => {
    const queryKey = ["task-system", "tasks", { status: ["TODO"] }];
    const client = makeQueryClient();
    client.setQueryData<TaskListResponse>(queryKey, makeResponse([makeTask({ id: 42, title: "Old" })]));
    mockedUpdate.mockRejectedValueOnce(new Error("nope"));

    const { result } = renderHook(() => useUpdateTaskSystemTask(), { wrapper: wrapperFor(client) });

    await act(async () => {
      await expect(result.current.mutateAsync({ taskId: 42, patch: { title: "New" } })).rejects.toThrow("nope");
    });

    const final = client.getQueryData<TaskListResponse>(queryKey);
    expect(final?.tasks[0]?.title).toBe("Old");
  });

  it("rolls back an optimistic delete when the request fails", async () => {
    const queryKey = ["task-system", "tasks", { status: ["TODO"] }];
    const client = makeQueryClient();
    client.setQueryData<TaskListResponse>(queryKey, makeResponse([makeTask({ id: 42 })]));
    mockedDelete.mockRejectedValueOnce(new Error("nope"));

    const { result } = renderHook(() => useDeleteTaskSystemTask(), { wrapper: wrapperFor(client) });

    await act(async () => {
      await expect(result.current.mutateAsync(42)).rejects.toThrow("nope");
    });

    const final = client.getQueryData<TaskListResponse>(queryKey);
    expect(final?.tasks).toHaveLength(1);
    expect(final?.tasks[0]?.id).toBe(42);
  });
});
