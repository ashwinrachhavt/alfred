import { ApiError, apiFetch } from "@/lib/api/client";
import { apiRoutes } from "@/lib/api/routes";
import type { TaskStatusResponse } from "@/lib/api/types/tasks";

export async function getTaskStatus(taskId: string): Promise<TaskStatusResponse> {
  try {
    return await apiFetch<TaskStatusResponse>(apiRoutes.tasks.status(taskId), {
      cache: "no-store",
    });
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) {
      return {
        task_id: taskId,
        status: "not_found",
        ready: true,
        successful: false,
        failed: true,
        result: null,
        error:
          "Task not found. If you restarted the backend, queued tasks may have been cleared. Run again to re-queue.",
      };
    }
    throw err;
  }
}
