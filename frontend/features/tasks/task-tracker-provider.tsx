"use client";

import * as React from "react";
import { useRouter } from "next/navigation";

import { useQueries, type Query } from "@tanstack/react-query";
import { toast } from "sonner";

import { getTaskStatus } from "@/lib/api/tasks";
import type { TaskStatusResponse } from "@/lib/api/types/tasks";

import {
  loadNotifiedTaskIds,
  loadTrackedTasks,
  saveNotifiedTaskIds,
  saveTrackedTasks,
  type TaskSource,
  type TrackedTask,
} from "@/features/tasks/task-tracker";

type TaskTrackerContextValue = {
  tasks: TrackedTask[];
  statusById: Record<string, TaskStatusResponse | undefined>;
  activeCount: number;
  isOnline: boolean;
  isTaskCenterOpen: boolean;
  setTaskCenterOpen: (open: boolean) => void;
  trackTask: (task: Omit<TrackedTask, "createdAt"> & { createdAt?: string }) => void;
  removeTask: (taskId: string) => void;
  clearCompleted: () => void;
};

const TaskTrackerContext = React.createContext<TaskTrackerContextValue | null>(null);

function useTaskTrackerContext(): TaskTrackerContextValue {
  const ctx = React.useContext(TaskTrackerContext);
  if (!ctx) throw new Error("useTaskTracker must be used within TaskTrackerProvider.");
  return ctx;
}

function defaultTaskHref(taskId: string): string {
  return `/tasks?taskId=${encodeURIComponent(taskId)}`;
}

function withDefaultHref(task: TrackedTask): TrackedTask {
  return {
    ...task,
    href: task.href ?? defaultTaskHref(task.id),
  };
}

function nextTaskLabel(source: TaskSource, label: string): string {
  const normalized = label.trim();
  if (normalized) return normalized;
  if (source === "company_research") return "Company research";
  if (source === "interview_prep") return "Interview prep";
  return "Background task";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object";
}

function extractCompanyResearchReportId(result: unknown): string | null {
  if (!isRecord(result)) return null;
  const id = typeof result.id === "string" ? result.id.trim() : "";
  if (!id) return null;
  return isRecord(result.report) ? id : null;
}

function extractCompanyResearchCompanyName(result: unknown): string | null {
  if (!isRecord(result)) return null;

  if (typeof result.company === "string" && result.company.trim()) {
    return result.company.trim();
  }

  const report = isRecord(result.report) ? result.report : null;
  if (report && typeof report.company === "string" && report.company.trim()) {
    return report.company.trim();
  }

  return null;
}

function deriveTaskHref(task: TrackedTask, status: TaskStatusResponse | undefined): string | null {
  if (!status?.ready || !status.successful) return null;
  if (!status.result) return null;
  if (task.source !== "company_research") return null;

  const reportId = extractCompanyResearchReportId(status.result);
  if (!reportId) return null;
  return `/company?reportId=${encodeURIComponent(reportId)}`;
}

function deriveTaskLabel(task: TrackedTask, status: TaskStatusResponse | undefined): string | null {
  if (!status?.ready || !status.successful) return null;
  if (!status.result) return null;
  if (task.source !== "company_research") return null;

  const company = extractCompanyResearchCompanyName(status.result);
  if (!company) return null;
  return `Company research: ${company}`;
}

function mergeTask(existing: TrackedTask, next: TrackedTask): TrackedTask {
  return {
    ...existing,
    ...next,
    // Preserve creation time for stable ordering.
    createdAt: existing.createdAt,
    // Preserve status if the next task doesn't include it.
    lastStatus: next.lastStatus ?? existing.lastStatus,
  };
}

function upsertTask(list: TrackedTask[], task: TrackedTask): TrackedTask[] {
  const normalized = withDefaultHref(task);
  const idx = list.findIndex((t) => t.id === normalized.id);
  if (idx === -1) return [normalized, ...list];
  return list.map((t, i) => (i === idx ? mergeTask(t, normalized) : t));
}

function stableSortByCreatedAtDesc(list: TrackedTask[]): TrackedTask[] {
  return [...list].sort((a, b) => b.createdAt.localeCompare(a.createdAt));
}

export function TaskTrackerProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();

  const [tasks, setTasks] = React.useState<TrackedTask[]>(() =>
    stableSortByCreatedAtDesc(loadTrackedTasks()),
  );
  const [isTaskCenterOpen, setTaskCenterOpen] = React.useState(false);
  const [isOnline, setIsOnline] = React.useState(() =>
    typeof navigator === "undefined" ? true : navigator.onLine,
  );

  const notifiedRef = React.useRef<Set<string>>(loadNotifiedTaskIds());
  const previousReadyRef = React.useRef<Record<string, boolean>>({});

  React.useEffect(() => {
    function onOnline() {
      setIsOnline(true);
    }
    function onOffline() {
      setIsOnline(false);
    }

    window.addEventListener("online", onOnline);
    window.addEventListener("offline", onOffline);
    return () => {
      window.removeEventListener("online", onOnline);
      window.removeEventListener("offline", onOffline);
    };
  }, []);

  const taskQueries = useQueries({
    queries: tasks.map((task) => ({
      queryKey: ["tasks", "status", task.id] as const,
      queryFn: () => getTaskStatus(task.id),
      enabled: isOnline,
      refetchInterval: (query: Query<TaskStatusResponse>) =>
        query.state.data?.ready ? false : 2000,
      retry: 1,
      staleTime: 0,
    })),
  });

  const statusById = React.useMemo(() => {
    const map: Record<string, TaskStatusResponse | undefined> = {};
    tasks.forEach((task, idx) => {
      map[task.id] = taskQueries[idx]?.data ?? task.lastStatus;
    });
    return map;
  }, [taskQueries, tasks]);

  const activeCount = React.useMemo(() => {
    return tasks.reduce((count, task) => {
      const status = statusById[task.id];
      if (!status || !status.ready) return count + 1;
      return count;
    }, 0);
  }, [statusById, tasks]);

  const persistTasks = React.useCallback((updater: (prev: TrackedTask[]) => TrackedTask[]) => {
    setTasks((prev) => {
      const next = stableSortByCreatedAtDesc(updater(prev));
      saveTrackedTasks(next);
      return next;
    });
  }, []);

  const trackTask = React.useCallback(
    (task: Omit<TrackedTask, "createdAt"> & { createdAt?: string }) => {
      const createdAt = task.createdAt ?? new Date().toISOString();
      const next: TrackedTask = {
        id: task.id.trim(),
        label: nextTaskLabel(task.source, task.label),
        source: task.source,
        createdAt,
        href: task.href,
        lastStatus: task.lastStatus,
      };

      if (!next.id) return;
      persistTasks((prev) => upsertTask(prev, next));
    },
    [persistTasks],
  );

  const removeTask = React.useCallback(
    (taskId: string) => {
      persistTasks((prev) => prev.filter((t) => t.id !== taskId));
    },
    [persistTasks],
  );

  const clearCompleted = React.useCallback(() => {
    persistTasks((prev) => prev.filter((task) => !statusById[task.id]?.ready));
  }, [persistTasks, statusById]);

  React.useEffect(() => {
    const patches: Record<string, Partial<TrackedTask>> = {};

    tasks.forEach((task) => {
      const isDefaultHref = (task.href ?? "") === defaultTaskHref(task.id);
      if (!isDefaultHref) return;
      const status = statusById[task.id];

      const href = deriveTaskHref(task, status);
      const label = deriveTaskLabel(task, status);

      if (!href && !label) return;
      const patch: Partial<TrackedTask> = {};
      if (href) patch.href = href;
      if (label) patch.label = label;
      patches[task.id] = patch;
    });

    const patchIds = Object.keys(patches);
    if (!patchIds.length) return;

    persistTasks((prev) =>
      prev.map((task) => {
        const patch = patches[task.id];
        if (!patch) return task;
        return { ...task, ...patch };
      }),
    );
  }, [persistTasks, statusById, tasks]);

  React.useEffect(() => {
    tasks.forEach((task) => {
      const status = statusById[task.id];
      if (!status) return;

      const wasReady = previousReadyRef.current[task.id] ?? false;
      const isReady = status.ready;
      previousReadyRef.current[task.id] = isReady;
      if (wasReady || !isReady) return;

      if (notifiedRef.current.has(task.id)) return;

      const title = task.label || "Background task";
      if (status.successful) {
        toast.success(`${title} complete`, {
          action: {
            label: "View",
            onClick: () => router.push(task.href ?? defaultTaskHref(task.id)),
          },
        });
      } else if (status.failed) {
        toast.error(`${title} failed`, {
          description: status.error ?? "Task failed.",
          action: {
            label: "View",
            onClick: () => router.push(task.href ?? defaultTaskHref(task.id)),
          },
        });
      } else {
        toast.message(`${title} finished`, {
          action: {
            label: "View",
            onClick: () => router.push(task.href ?? defaultTaskHref(task.id)),
          },
        });
      }

      notifiedRef.current.add(task.id);
      saveNotifiedTaskIds(notifiedRef.current);

      // Persist last known status for offline display without re-rendering.
      saveTrackedTasks(tasks.map((t) => (t.id === task.id ? { ...t, lastStatus: status } : t)));
    });
  }, [router, statusById, tasks]);

  const value = React.useMemo<TaskTrackerContextValue>(
    () => ({
      tasks,
      statusById,
      activeCount,
      isOnline,
      isTaskCenterOpen,
      setTaskCenterOpen,
      trackTask,
      removeTask,
      clearCompleted,
    }),
    [
      activeCount,
      clearCompleted,
      isOnline,
      isTaskCenterOpen,
      removeTask,
      statusById,
      tasks,
      trackTask,
    ],
  );

  return <TaskTrackerContext.Provider value={value}>{children}</TaskTrackerContext.Provider>;
}

export function useTaskTracker() {
  return useTaskTrackerContext();
}
