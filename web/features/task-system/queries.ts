import { useQuery } from "@tanstack/react-query";

import {
  ensureTaskSystemDefaultBoard,
  listTaskSystemBoards,
  listTaskSystemColumns,
  listTaskSystemTasks,
} from "@/lib/api/task-system";
import type { TaskPriority, TaskStatus } from "@/features/task-system/types";

export const taskSystemKeys = {
  all: ["task-system"] as const,
  tasks: ["task-system", "tasks"] as const,
  taskList: (params: TaskListParams) => ["task-system", "tasks", normalizeTaskListParams(params)] as const,
  boards: ["task-system", "boards"] as const,
  columns: (boardId: number | null | undefined) => ["task-system", "boards", boardId, "columns"] as const,
  rewards: ["task-system", "rewards"] as const,
  calendar: ["task-system", "calendar"] as const,
};

export type TaskListParams = {
  status?: TaskStatus[];
  priority?: TaskPriority[];
  board_id?: number;
  project_id?: number;
  source_kind?: string;
  limit?: number;
  offset?: number;
  enabled?: boolean;
};

export function normalizeTaskListParams(params: TaskListParams): Record<string, unknown> {
  const normalized: Record<string, unknown> = {};
  if (params.status?.length) normalized.status = [...params.status].sort();
  if (params.priority?.length) normalized.priority = [...params.priority].sort();
  if (params.board_id !== undefined) normalized.board_id = params.board_id;
  if (params.project_id !== undefined) normalized.project_id = params.project_id;
  if (params.source_kind) normalized.source_kind = params.source_kind;
  if (params.limit !== undefined) normalized.limit = params.limit;
  if (params.offset !== undefined) normalized.offset = params.offset;
  return normalized;
}

export function useTaskSystemTasks(params: TaskListParams = {}) {
  const { enabled, ...listParams } = params;
  return useQuery({
    enabled: enabled !== false,
    queryKey: taskSystemKeys.taskList(listParams),
    queryFn: () => listTaskSystemTasks(listParams),
    staleTime: 30_000,
    placeholderData: (previous) => previous,
  });
}

export function useTaskSystemBoards() {
  return useQuery({
    queryKey: taskSystemKeys.boards,
    queryFn: listTaskSystemBoards,
    staleTime: 60_000,
  });
}

export function useTaskSystemDefaultBoard() {
  return useQuery({
    queryKey: [...taskSystemKeys.boards, "default"],
    queryFn: ensureTaskSystemDefaultBoard,
    staleTime: 60_000,
  });
}

export function useTaskSystemColumns(boardId: number | null | undefined) {
  return useQuery({
    enabled: typeof boardId === "number",
    queryKey: taskSystemKeys.columns(boardId),
    queryFn: () => listTaskSystemColumns(boardId as number),
    staleTime: 60_000,
  });
}
