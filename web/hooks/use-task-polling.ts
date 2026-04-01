"use client";

import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api/client";
import { apiRoutes } from "@/lib/api/routes";

interface TaskStatus {
  task_id: string;
  status: "pending" | "running" | "completed" | "failed";
  result: unknown;
  error: string | null;
}

/**
 * Poll a Celery task status until it reaches a terminal state.
 * Polls every 2s while pending/running, stops on completed/failed.
 */
export function useTaskPolling(taskId: string | null) {
  return useQuery<TaskStatus>({
    queryKey: ["task-status", taskId],
    queryFn: () => apiFetch<TaskStatus>(apiRoutes.tasks.status(taskId!), { cache: "no-store" }),
    enabled: Boolean(taskId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "completed" || status === "failed") return false;
      return 2000;
    },
    staleTime: 0,
  });
}
