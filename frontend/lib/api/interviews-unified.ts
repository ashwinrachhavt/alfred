import { apiFetch, apiPostJson } from "@/lib/api/client";
import { apiRoutes } from "@/lib/api/routes";
import type {
  EnqueueUnifiedInterviewTaskResponse,
  UnifiedInterviewRequest,
  UnifiedInterviewResponse,
} from "@/lib/api/types/interviews-unified";

function normalizeTaskStatusUrl(statusUrl: string): string {
  if (!statusUrl) return statusUrl;

  // Backend sometimes returns `/tasks/:id` while the frontend consistently calls `/api/tasks/:id`.
  if (statusUrl.startsWith("/api/tasks/")) return statusUrl;
  if (statusUrl.startsWith("/tasks/"))
    return `${apiRoutes.tasks.status("")}${statusUrl.slice("/tasks/".length)}`;

  try {
    const parsed = new URL(statusUrl);
    const pathname = parsed.pathname;
    if (pathname.startsWith("/tasks/")) {
      const taskId = pathname.slice("/tasks/".length);
      return `${apiRoutes.tasks.status(taskId)}${parsed.search}`;
    }
  } catch {
    // Not an absolute URL; fall back to the raw value.
  }

  return statusUrl;
}

export async function processUnifiedInterview(
  payload: UnifiedInterviewRequest,
  options?: { background?: boolean },
): Promise<UnifiedInterviewResponse | EnqueueUnifiedInterviewTaskResponse> {
  const background = options?.background ? "?background=true" : "";
  return apiPostJson<
    UnifiedInterviewResponse | EnqueueUnifiedInterviewTaskResponse,
    UnifiedInterviewRequest
  >(`/api/interviews-unified/process${background}`, payload, { cache: "no-store" });
}

export async function getTaskStatus<TResponse>(statusUrl: string): Promise<TResponse> {
  return apiFetch<TResponse>(normalizeTaskStatusUrl(statusUrl), { cache: "no-store" });
}
