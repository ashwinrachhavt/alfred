import { apiFetch } from "@/lib/api/client";
import { apiRoutes } from "@/lib/api/routes";
import type { TaskStatusResponse } from "@/lib/api/types/tasks";

export async function getTaskStatus(taskId: string): Promise<TaskStatusResponse> {
  return apiFetch<TaskStatusResponse>(apiRoutes.tasks.status(taskId), { cache: "no-store" });
}
