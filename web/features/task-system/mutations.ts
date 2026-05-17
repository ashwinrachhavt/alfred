import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  completeTaskSystemFocusSession,
  completeTaskSystemPomodoro,
  createTaskSystemTask,
  deleteTaskSystemTask,
  markTaskSystemTaskDone,
  moveTaskSystemTask,
  planTaskSystemTasks,
  scheduleTaskSystemFocusBlock,
  startTaskSystemFocusSession,
  startTaskSystemPomodoro,
  updateTaskSystemTask,
} from "@/lib/api/task-system";
import type {
  TaskCalendarEventCreate,
  TaskCreate,
  TaskFocusSessionCreate,
  TaskItem,
  TaskMoveRequest,
  TaskPlanRequest,
  TaskPomodoroCreate,
  TaskUpdate,
} from "@/features/task-system/types";
import { taskSystemKeys } from "@/features/task-system/queries";

type TaskSnapshot = {
  queryKey: readonly unknown[];
  data: { tasks?: TaskItem[] };
};

function invalidateTaskSystem(queryClient: ReturnType<typeof useQueryClient>): void {
  void queryClient.invalidateQueries({ queryKey: taskSystemKeys.all });
  void queryClient.invalidateQueries({ queryKey: ["today"] });
}

function snapshotTaskLists(queryClient: ReturnType<typeof useQueryClient>): TaskSnapshot[] {
  return queryClient
    .getQueryCache()
    .findAll({ queryKey: taskSystemKeys.tasks })
    .flatMap((query) => {
      const data = query.state.data as { tasks?: TaskItem[] } | undefined;
      return data?.tasks ? [{ queryKey: query.queryKey, data }] : [];
    });
}

export function useCreateTaskSystemTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: TaskCreate) => createTaskSystemTask(payload),
    onSuccess: () => invalidateTaskSystem(queryClient),
  });
}

export function useUpdateTaskSystemTask() {
  const queryClient = useQueryClient();
  return useMutation<TaskItem, Error, { taskId: number; patch: TaskUpdate }, { snapshots: TaskSnapshot[] }>({
    mutationFn: ({ taskId, patch }) => updateTaskSystemTask(taskId, patch),
    onMutate: async ({ taskId, patch }) => {
      await queryClient.cancelQueries({ queryKey: taskSystemKeys.tasks });
      const snapshots = snapshotTaskLists(queryClient);
      for (const { queryKey, data } of snapshots) {
        queryClient.setQueryData(queryKey, {
          ...data,
          tasks: data.tasks?.map((task) => (task.id === taskId ? { ...task, ...patch } : task)),
        });
      }
      return { snapshots };
    },
    onError: (_error, _variables, context) => {
      for (const snapshot of context?.snapshots ?? []) {
        queryClient.setQueryData(snapshot.queryKey, snapshot.data);
      }
    },
    onSettled: () => invalidateTaskSystem(queryClient),
  });
}

export function useDeleteTaskSystemTask() {
  const queryClient = useQueryClient();
  return useMutation<unknown, Error, number, { snapshots: TaskSnapshot[] }>({
    mutationFn: (taskId) => deleteTaskSystemTask(taskId),
    onMutate: async (taskId) => {
      await queryClient.cancelQueries({ queryKey: taskSystemKeys.tasks });
      const snapshots = snapshotTaskLists(queryClient);
      for (const { queryKey, data } of snapshots) {
        queryClient.setQueryData(queryKey, {
          ...data,
          tasks: data.tasks?.filter((task) => task.id !== taskId),
        });
      }
      return { snapshots };
    },
    onError: (_error, _variables, context) => {
      for (const snapshot of context?.snapshots ?? []) {
        queryClient.setQueryData(snapshot.queryKey, snapshot.data);
      }
    },
    onSettled: () => invalidateTaskSystem(queryClient),
  });
}

export function useMarkTaskSystemTaskDone() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ taskId, reflection }: { taskId: number; reflection?: string }) =>
      markTaskSystemTaskDone(taskId, reflection),
    onSuccess: () => invalidateTaskSystem(queryClient),
  });
}

export function useMoveTaskSystemTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ taskId, payload }: { taskId: number; payload: TaskMoveRequest }) =>
      moveTaskSystemTask(taskId, payload),
    onSuccess: () => invalidateTaskSystem(queryClient),
  });
}

export function usePlanTaskSystemTasks() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: TaskPlanRequest) => planTaskSystemTasks(payload),
    onSuccess: (result) => {
      if (result.created_tasks.length > 0) invalidateTaskSystem(queryClient);
    },
  });
}

export function useScheduleTaskSystemFocusBlock() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: TaskCalendarEventCreate) => scheduleTaskSystemFocusBlock(payload),
    onSuccess: () => invalidateTaskSystem(queryClient),
  });
}

export function useStartTaskSystemFocusSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: TaskFocusSessionCreate) => startTaskSystemFocusSession(payload),
    onSuccess: () => invalidateTaskSystem(queryClient),
  });
}

export function useCompleteTaskSystemFocusSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ sessionId, ended_at, interruptions }: { sessionId: number; ended_at?: string; interruptions?: number }) =>
      completeTaskSystemFocusSession(sessionId, { ended_at, interruptions }),
    onSuccess: () => invalidateTaskSystem(queryClient),
  });
}

export function useStartTaskSystemPomodoro() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: TaskFocusSessionCreate) => startTaskSystemPomodoro(payload),
    onSuccess: () => invalidateTaskSystem(queryClient),
  });
}

export function useCompleteTaskSystemPomodoro() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: TaskPomodoroCreate) => completeTaskSystemPomodoro(payload),
    onSuccess: () => invalidateTaskSystem(queryClient),
  });
}
